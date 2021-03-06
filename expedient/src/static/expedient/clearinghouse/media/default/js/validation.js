var DESCRIPTION_RE = /^([0-9a-zA-Z\-\_\ \.\,\;\[\]\{\}\=\#\$\%\&\/\(\)\!\?\"\'\r\n])+$/;
var NOTBLANK_RE = /^.+$/;
var NUMBER_RE = /^([0-9])+$/;
var RESOURCE_RE = /^([0-9a-zA-Z\-\_\ \.])+$/;
//var RESOURCE_RE = /^([0-9a-zA-Z\-\_])+$/;
var RESOURCE_RESTRICTED_RE = /^([0-9a-zA-Z\-]){1,64}$/;
var USERNAME_RE = /^([0-9a-zA-Z\-\_])+$/;

/* Error list check and generation */
function doErrorlistExists(fieldID) {
    var result = false;
    if ($("#errorlist_" + fieldID).length > 0) {
        result = true;
    }
    return result;
}

function prependErrorlist(fieldID, errorMessage) {
    $("#" + fieldID).parent().prepend("<ul id=\"errorlist_" + fieldID + "\" class=\"error\"><li>" + errorMessage + "</li></ul>");
}

function removeErrorlist(fieldID) {
    $("#errorlist_" + fieldID).remove();
}

/* REGEX wrapper */
function checkWithRegExp(fieldID, regExp, errorMessage) {
    var result = false;
    var reCorrectFormat = new RegExp(regExp);
    var field = $("#" + fieldID);
    if (!reCorrectFormat.test(field.val())) {
        if (!doErrorlistExists(field.attr("id"))) {
            prependErrorlist(field.attr("id"), errorMessage);
        }
    } else {
        if (doErrorlistExists(field.attr("id"))) {
            removeErrorlist(field.attr("id"));
        }
        result = true;
    }
    return result;
}

/* Generic validation */
function checkDescription(id, resourceName) {
    return checkWithRegExp(id, DESCRIPTION_RE, "Check that the " + resourceName + " has ASCII characters only.");
}

function checkNotBlank(id, resourceName) {
    return checkWithRegExp(id, NOTBLANK_RE, "Check that the " + resourceName + " is not empty.");
}

function checkNumber(id, resourceName) {
    return checkWithRegExp(id, NUMBER_RE, "Check that the " + resourceName + " consists only of numbers.");
}

function checkRestrictedName(id, resourceName) {
    return checkWithRegExp(id, RESOURCE_RESTRICTED_RE, "Check that the " + resourceName + " has ASCII characters only and no whitespaces.");
}

function checkName(id, resourceName) {
    return checkWithRegExp(id, RESOURCE_RE, "Check that the " + resourceName + " has ASCII characters only.");
}

function checkUserName(id, resourceName) {
    return checkWithRegExp(id, USERNAME_RE, "Check that the " + resourceName + " has ASCII characters only.");
}

function checkAllResultsOK(results) {
    var result = true;
    $.each(results, function(index, value) { result = result && value; });
    return result;
}

function checkDropDownSelected(fieldID) {
    var result = false;
    var field = $("#" + fieldID);
    if ($("#" + fieldID).attr("selectedIndex") <= 0) {
        if (!doErrorlistExists(field.attr("id"))) {
            prependErrorlist(field.attr("id"), "Please select one option.");
        }
    } else {
        if (doErrorlistExists(field.attr("id"))) {
            removeErrorlist(field.attr("id"));
        }
        result = true;
    }
    return result;
}

/* Automated validation */
function contains(substring, string) {
    return (string != undefined && substring != undefined && string.indexOf(substring) > -1);
}

/* Bind validation check to the submit button */
$(":submit[id^=form_create], :submit[id^=form_update], :button[id^=form_create], :button[id^=form_update]").click(function() {
    // First, submit ID
    var submitID = $(this).attr("id") || "";
    if (contains("form_create_", submitID)) {
        submitID = submitID.split('form_create_').slice(1).join('')
    } else if (contains("form_update_", submitID)) {
        submitID = submitID.split('form_update_').slice(1).join('')
    }

    // Second, all other input IDs
    var id = "";
    var type = "";
    var results = Array();
    $("form table input, form table select, form table textarea").each(function(index) {
        id = $(this).attr("id") || "";
        type = $(this).attr("type") || "";
        // Correct by default (ignores fields non stated in the if/else block
        results[index] = true;
        if (contains("text",type)) {
            if (contains("username",id)) {
                results[index] = checkUserName(id,submitID + " username");
            } else if (contains("name",id) && submitID == "VM") {
                // VM names have a special treatment
                results[index] = checkRestrictedName(id,submitID + " name");
            } else if (contains("name",id)) {
                results[index] = checkName(id,submitID + " name");
            } else if (contains("description",id)) {
                results[index] = checkDescription(id,submitID + " description");
            } else if (contains("location",id)) {
                results[index] = checkDescription(id,submitID + " location");
            } else if (contains("memory",id)) {
                results[index] = checkNumber(id,submitID + " memory");
            } else if (contains("url",id)) {
                results[index] = checkNotBlank(id,submitID + " URL");
            }
        } else if (contains("select",type)) {
            results[index] = checkDropDownSelected(id);
        }
    });
    return checkAllResultsOK(results);
});
