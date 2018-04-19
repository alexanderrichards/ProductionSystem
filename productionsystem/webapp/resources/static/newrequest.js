$(document).ready(function() {
    $("form").submit(function(event){
	event.preventDefault();  // prevent default submission as doesn't create json content.
	$.ajax({url: "/requests",
		type: "POST",
		data: JSON.stringify($(this).serializeArray()),
		contentType: "application/json; charset=utf-8",
		error: function(request, status, error){
		    console.warn(`Error submitting request!\nstatus: ${status}\nerror: ${error}\nrequest: ` + JSON.stringify(request));
		    parent.bootstrap_alert("Attention!", `Error submitting request! status: ${status} error: ${error}`, "alert-danger");
		},
		success: function(result){
		    console.log("Successfully posted request.");
		    parent.refresh_table();
		    parent.bootstrap_alert("Success!", "Request added", "alert-success");
		}
	       });
	parent.$.fancybox.close();
    });
});
