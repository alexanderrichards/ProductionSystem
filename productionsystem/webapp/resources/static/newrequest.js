$(document).ready(function() {
    $("form").submit(function(event){
	event.preventDefault();  // prevent default submission as doesn't create json content.
	var form_data = new Object();
	$.each($(this).serializeArray(), function(index, mapping){
	    form_data[mapping.name] = mapping.value;
	});
    var data = {"request":{"description": "new request"}, "parametricjobs": []};
	$.ajax({url: "/requests",
		type: "POST",
		data: JSON.stringify(data),
		contentType: "application/json; charset=utf-8",
		error: function(request, status, error){
		    console.warn(`Error submitting request!\nstatus: ${status}\nerror: ${error}\nrequest: ` + JSON.stringify(request));
		    parent.bootstrap_alert("Attention!", `Error submitting request! status: ${status} error: ${error}`, "alert-danger");
		},
		success: function(result){
		    console.log("Successfully posted request.");
		    parent.bootstrap_alert("Success!", "Request added", "alert-success");
		}
	       });
	parent.$.fancybox.close();
    });
});
