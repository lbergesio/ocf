import logging
from pprint import pformat

from django.views.generic import simple
from django.shortcuts import get_object_or_404
from django.http import HttpResponseRedirect, HttpResponseNotAllowed,\
    HttpResponse
from django.forms.models import modelformset_factory
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django import forms
from django.db.models import Q
from django.views.generic.create_update import get_model_and_form_class

import copy
from vt_plugin.models import VtPlugin, VTServer, VM, Action
from vt_plugin.forms.VM import VMModelForm
from vt_manager.communication.utils.XmlHelper import XmlHelper
from vt_plugin.utils.Translator import Translator
import xmlrpclib, uuid
from vt_plugin.utils.ServiceThread import *
from vt_plugin.controller.dispatchers.ProvisioningDispatcher import *
from vt_plugin.controller.VMcontroller.VMcontroller import *
from vt_plugin.utils.ServiceThread import *
from expedient.clearinghouse.aggregate.models import Aggregate
from expedient.common.messaging.context_processors import messaging
from expedient.common.messaging.models import DatedMessage

def goto_create_vm(request, slice_id, agg_id):
    """Show a page that allows user to add SSH s to the aggregate."""

    if request.method == "POST":
        # Shows error message when Aggregate is unreachable, disable VM creation and get back to slice detail page
        agg = Aggregate.objects.get(id = agg_id)
        if agg.check_status() == False:
            DatedMessage.objects.post_message_to_user(
                "VM Aggregate '%s' is not available" % agg.name,
                request.user, msg_type=DatedMessage.TYPE_ERROR,)
            return HttpResponseRedirect(reverse("slice_detail",args=[slice_id]))

        if 'create_vms' in request.POST:
            server_id=request.POST['selected_server_'+agg_id]
            return HttpResponseRedirect(reverse("virtualmachine_crud",
                                                args=[slice_id,server_id]))
        else:
            return HttpResponseRedirect("/")

#TODO: put the plugin code in plugin package!!!
def virtualmachine_crud(request, slice_id, server_id):

    """Show a page that allows user to add VMs to the VT server."""
    error_crud = ""
    serv = get_object_or_404(VTServer, id = server_id)
    slice = get_object_or_404(Slice, id = slice_id)
    virtualmachines = VM.objects.filter(sliceId=slice.uuid)

    # Creates a model based on VM
    VMModelFormAux = modelformset_factory(
        VM, can_delete=False, form=VMModelForm,
        fields=["name", "memory","disc_image", "hdSetupType", "virtualizationSetupType"],
    )

    try:
        if request.method == "POST":
            if 'create_new_vms' in request.POST:
                # "Done" pressed ==> send xml to AM
                formset = VMModelFormAux(request.POST, queryset=virtualmachines)
                if formset.is_valid():
                    instances = formset.save(commit=False)
                    #create virtualmachines from received formulary
                    VMcontroller.processVMCreation(instances, serv.uuid, slice, request.user)
#                    return HttpResponseRedirect(reverse("html_plugin_home",
                    return HttpResponseRedirect(reverse("slice_detail",
                                                args=[slice_id]))
                # Form not valid => raise error
                else:
                    raise ValidationError("Invalid input: either VM name contains non-ASCII characters, underscores, whitespaces or the memory is not a number or less than 128Mb.", code="invalid",)

        else:
            formset = VMModelFormAux(queryset=VM.objects.none())

    except ValidationError as e:
        # Django exception message handling is different to Python's...
        error_crud = ";".join(e.messages)
    except Exception as e:
        print "normal exception here: %s" % str(e)
        DatedMessage.objects.post_message_to_user(
            "VM might have been created, but some problem ocurred: %s" % str(e),
            request.user, msg_type=DatedMessage.TYPE_ERROR)
        return HttpResponseRedirect(reverse("home"))

    return simple.direct_to_template(
        request, template="aggregate_add_virtualmachines.html",
        extra_context={"virtual_machines": virtualmachines, "exception": error_crud,
                        "server_name": serv.name, "formset": formset,"slice":slice,
                        "breadcrumbs": (
                    ("Home", reverse("home")),
                    ("Project %s" % slice.project.name, reverse("project_detail", args=[slice.project.id])),
                    ("Slice %s" % slice.name, reverse("slice_detail", args=[slice_id])),
#                   #("Resource visualization panel ", reverse("html_plugin_home", args=[slice_id])),
                    ("Create VM in server %s" %serv.name, reverse("virtualmachine_crud", args=[slice_id, server_id])),
                )
        })

def manage_vm(request, slice_id, vm_id, action_type):

    "Manages the actions executed over VMs at url manage resources."

    vm = VM.objects.get(id = vm_id)
    #if action_type == 'stop' : action_type = 'hardStop'
    rspec = XmlHelper.getSimpleActionSpecificQuery(action_type, vm.serverID)
    Translator.PopulateNewAction(rspec.query.provisioning.action[0], vm)

    ServiceThread.startMethodInNewThread(ProvisioningDispatcher.processProvisioning,rspec.query.provisioning, request.user)

    #set temporally status
    #vm.state = "on queue"
    if action_type == 'start':
        vm.state = 'starting...'
    elif action_type == 'stop':
        vm.state = 'stopping...'
    elif action_type == 'reboot':
        vm.state = 'rebooting...'
    elif action_type == 'delete':
        vm.state = 'deleting...'
    elif action_type == 'create':
        vm.state = 'creating...'
    vm.save()
    #go to manage resources again
    #return HttpResponseRedirect(reverse("html_plugin_home",args=[slice_id]))
    response = HttpResponse("")
    return response


def check_vms_status(request, slice_id):
    from django.utils import simplejson
    vmsStatus = {}
    vmsActionsHtmlCodes = {}
    vmsIP = {}
    slice = get_object_or_404(Slice, id=slice_id)
    vt_aggs = \
            slice.aggregates.filter(
                leaf_name=VtPlugin.__name__.lower())
    for agg in vt_aggs:
        for server in agg.resource_set.all():
            if server.leaf_name == 'VTServer':
                for vm in server.as_leaf_class().vms.all():
                    vmsStatus[str(vm.id)]= vm.state
                    if vm.state == "running":
                        actionsHtmlCode =\
                        "<div>\
                        <a href=\"#/\" onclick=\"handleVMaction("+str(slice.id)+","+str(vm.id)+",\'stop\')\">Stop</a> |\
                        <a href=\"#/\" onclick=\"handleVMaction("+str(slice.id)+","+str(vm.id)+",\'reboot\')\">Reboot</a>\
                        </div>"
                    elif  vm.state == "created (stopped)" :
                        actionsHtmlCode =\
						"<div>\
                        <a href=\"#/\" onclick=\"handleVMaction("+str(slice.id)+","+str(vm.id)+",\'start\')\">Start</a> |\
                        <a href=\"#/\" onclick=\"handleVMaction("+str(slice.id)+","+str(vm.id)+",\'delete\',\'"+str(vm.name)+"\')\">Delete</a>\
                        </div>"
                    elif vm.state == "stopped" :
                        actionsHtmlCode =\
                        "<div>\
                        <a href=\"#/\" onclick=\"handleVMaction("+str(slice.id)+","+str(vm.id)+",\'start\')\">Start</a> |\
                        <a href=\"#/\" onclick=\"handleVMaction("+str(slice.id)+","+str(vm.id)+",\'delete\',\'"+str(vm.name)+"\')\">Delete</a>\
                        </div>"
                    else:
                        actionsHtmlCode = "<div><img src=\"/static/media/default/img/loading.gif\" align=\"absmiddle\"></div>"
                    vmsActionsHtmlCodes[str(vm.id)] = actionsHtmlCode
                    try:
                        vmsIP[str(vm.id)]= vm.ifaces.get(isMgmt = True).ip
                    except:
                        pass
        
    data = simplejson.dumps({'status': vmsStatus, 'actions': vmsActionsHtmlCodes, 'ips': vmsIP,})
    response = HttpResponse(data)
    return response


def startStopSlice(action,uuid):

    "Manages the actions executed over VMs at url manage resources."
    try: 
        vmsToStart = VM.objects.filter(sliceId = uuid)
    
        #if action_type == 'stop' : action_type = 'hardStop'
        globalRspec = XmlHelper.getSimpleActionSpecificQuery(action, "dummy")
    	globalRspec.query.provisioning.action.pop()
        for vm in vmsToStart:
            rspec = XmlHelper.getSimpleActionSpecificQuery(action, vm.serverID)
            Translator.PopulateNewAction(rspec.query.provisioning.action[0], vm)
            globalRspec.query.provisioning.action.append(copy.deepcopy(rspec.query.provisioning.action[0]))
    
        ServiceThread.startMethodInNewThread(ProvisioningDispatcher.processProvisioning,globalRspec.query.provisioning, None)
    
        for vm in vmsToStart:
            if action == 'start':
            	vm.state = 'starting...'
            elif action == 'stop':
                vm.state = 'stopping'
            vm.save()
    except Exception as e:
        print e
        raise e


def update_messages(request):
    return simple.direct_to_template(
        request,
        template="messages_panel.html",
        extra_context=messaging(request),
    )

