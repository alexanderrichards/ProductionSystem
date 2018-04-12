$(document).ready(function() {

    refresh_table = function(){
      $.ajax({
        url: "/requests",
        type: "GET",
        cache: true,
        dataType: "json",
        error: function(request, status, error){
          console.warn(`Error getting table data!\nstatus: ${status}\nerror: ${error}\nrequest: ` + JSON.stringify(request));
        },
        statusCode: {
          400: function() {
            console.warn("Bad request! Request can probably not be cast to integer.");
          }
        },
        success: function(response, status, request){
          $("#tableBody").DataTable({data: response,
                                     autoWidth: false,
                                     order: JSON.parse(request.getResponseHeader('Datatable-Order')),
                                     columns: JSON.parse(request.getResponseHeader('Datatable-Columns')),
                                     columnDefs: [{targets: "_all", className: "dt-body-left dt-head-left",
                                                   render: function(data, type, row){
                                                     return data.length > 40 ? data.substr( 0, 40 ) +'…' : data;
                                                   }
                                                  }]
                                     })
        }
      });
    };

    // Reload table ajax every 5 mins
    /////////////////////////////////////////////////////
    setInterval(refresh_table(), 300000);  // 5 mins


    // Reschedule macros
    /////////////////////////////////////////////////////
    $("#tableBody tbody").on("click", "span.reschedule", function(){
	var macro_id = $(this).attr('macroid');
	var subtable = $(this).closest("table").DataTable();
//	var request_id = $(this).attr('requestid');
	$.ajax({url: `/parametricjobs/${macro_id}`,
		type: "PUT",
		data: {'reschedule': true},
		success: function(){
		    subtable.ajax.reload();
		}});

/*     $.ajax({url: '/parametricjobs/' + macro_id,
		type: "PUT",
		data: {'reschedule': true},
		success: function() {
		    $("#tableBody").DataTable().ajax.reload();
		    var datatable = $("#tableBody").DataTable();
		    var row_id = $("tr td.rowid:contains('"+ request_id +"')");
		    var tr = row_id.closest("tr");
		    var row = datatable.row(tr);
		    $.ajax({url: '/parametricjobs/' + request_id,
			    type: "GET",
			    success: function(data) {
				row.child(data).show();
			    }});
		}});
*/
    });

    // Table row details subtable show/hide
    /////////////////////////////////////////////////////
    function formatoutput(parametricjob){
	var output = '';
	if (parametricjob.sim_lfn_outputdir != null){
	    output = output.concat(parametricjob.sim_lfn_outputdir + "<br>");
	}
	if (parametricjob.mctruth_lfn_outputdir != null){
	    output = output.concat(parametricjob.mctruth_lfn_outputdir + "<br>");
	}
	if (parametricjob.reduction_lfn_outputdir != null){
	    output = output.concat(parametricjob.reduction_lfn_outputdir + "<br>");
	}
	if (parametricjob.der_lfn_outputdir != null){
	    output = output.concat(parametricjob.der_lfn_outputdir + "<br>");
	}
	if (parametricjob.lzap_lfn_outputdir != null){
	    output = output.concat(parametricjob.lzap_lfn_outputdir + "<br>");
	}
	return output;
    }

    function formatprogress(parametricjob){
	var striped = parametricjob.num_running + parametricjob.num_submitted > 0? "progress-bar-striped active": "";
	var percent_completed = 100 * parametricjob.num_completed / parametricjob.njobs;
	var percent_failed = 100 * parametricjob.num_failed / parametricjob.njobs;
	var percent_running = 100 * parametricjob.num_running / parametricjob.njobs;
	var percent_submitted = 100 * parametricjob.num_submitted / parametricjob.njobs;
	var num_other = parametricjob.njobs - (parametricjob.num_submitted + parametricjob.num_running + parametricjob.num_completed + parametricjob.num_failed)
	var percent_other = 100 * num_other / parametricjob.njobs;
	return `
            <div class="container" style="width:150px;border:0px;padding:0px;padding-top:15px">
              <div class="progress" style="background:rgba(214, 214, 214, 1)">
                <div class="progress-bar progress-bar-success ${striped}" role="progressbar" style="width:${percent_completed}%">
                  ${parametricjob.num_completed}
                </div>
                <div class="progress-bar progress-bar-danger ${striped}" role="progressbar" style="width:${percent_failed}%">
                  ${parametricjob.num_failed}
                </div>
                <div class="progress-bar progress-bar-info ${striped}" role="progressbar" style="width:${percent_running}%">
                  ${parametricjob.num_running}
                </div>
                <div class="progress-bar progress-bar-warning ${striped}" role="progressbar" style="width:${percent_submitted}%">
                  ${parametricjob.num_submitted}
                </div>
                <div class="progress-bar ${striped}" role="progressbar" style="width:${percent_other}%;background:grey">
                  ${num_other}
                </div>
              </div>
            </div>`;
    }

    function formatreschedule(parametricjob){
       return `<span class="glyphicon glyphicon-repeat text-primary reschedule" style="cursor:pointer" macroid="${parametricjob.id}" requestid="${parametricjob.request_id}"></span>`;
    }

    $("#tableBody tbody").on("click", "tr td span.details-control", function() {
	var datatable = $("#tableBody").DataTable();
	var tr = $(this).closest("tr");
	var row = datatable.row(tr);
	var request_id = datatable.cell(row, $("td.rowid", tr)).data();
	if (row.child.isShown()){
            row.child.hide();
	}
	else{
            row.child($("<table>", {id: "subtable-" + request_id})).show()
            $("#subtable-" + request_id).DataTable({ajax: {url: '/parametricjobs/' + request_id,
                                                           type: "GET",
                                                           cache: true,
                                                           dataSrc: function(json) {
							       var return_data = new Array();
							       var data = json.data
							       for(var i=0;i< data.length; i++){
								   return_data.push({
								       'macro': data[i].macro,
								       'njobs': data[i].njobs,
								       'nevents': data[i].nevents,
								       'seed': data[i].seed,
								       'output': formatoutput(data[i]),
								       'status': data[i].reschedule? 'Rescheduled': data[i].status,
								       'progress': formatprogress(data[i]),
								       'reschedule': data[i].status == 'Failed'? formatreschedule(data[i]): ''
								   })
							       }
							       return return_data;
							   }},
                                                    autoWidth: true,
                                                    paging: false,
                                                    searching: false,
                                                    info: false,
                                                    //columnDefs: [ { defaultContent: "-", data: null, targets: "_all" } ],
                                                    columns: [
							{ data: 'macro', title: 'Macro' },
							{ data: 'njobs', title: 'NJobs' },
							{ data: 'nevents', title: 'NEvents' },
							{ data: 'seed', title: 'Seed' },
							{ data: 'output', title: 'Output' },
							{ data: 'status', title: 'Status' },
							{ data: 'progress', title: 'Progress' },
							{ data: 'reschedule', orderable: false }
                                                    ],
						    order: [[5, 'desc']]
                                                   });
	}
	$(this).toggleClass("glyphicon-plus-sign")
	$(this).toggleClass("glyphicon-minus-sign")
	$(this).toggleClass("text-primary")
	$(this).toggleClass("text-danger")
    });

    /////////////////////////////////////////////////////

    // New request button
    /////////////////////////////////////////////////////
    $("#NewRequest").fancybox({
	type: "iframe",
	href: "/newrequest.html",
	title: "Submit New Request"
    });
    /////////////////////////////////////////////////////

    // Double click a row
    /////////////////////////////////////////////////////
    $("#tableBody tbody").on("dblclick", "tr", function(e){
	$.fancybox({
            type: "ajax",
            href: "/requests/" + $("#tableBody").DataTable().cell($(this), $("td.rowid", this)).data()
	});
    });
    /////////////////////////////////////////////////////

    // Admins button
    /////////////////////////////////////////////////////
    $("#Admins").fancybox({
	type: "ajax",
	href: "/admins",
	title: "Admin Management",
	afterClose: function(){location.reload();}
    });
    /////////////////////////////////////////////////////

    // Table row selection
    /////////////////////////////////////////////////////
    var last_selected = 0;
    $("#tableBody tbody").on("click", "tr", function(e){
	var table_body = $("#tableBody tbody");
	var table_rows = $("#tableBody tbody tr");
        var new_selected = $(table_rows).index($(this));
	if (!e.ctrlKey && !e.shiftKey) {
	    $("tr.selected", $(table_body)).removeClass("selected");
        }
	else if (e.shiftKey) {
            if (new_selected < last_selected) {
                var length = $(table_rows).size() - 1;
                $(table_rows).slice(new_selected - length, last_selected - length - 1).addClass("selected");
            }
	    $(table_rows).slice(last_selected + 1, new_selected).addClass("selected");
	}
	$(this).toggleClass("selected");
        last_selected = new_selected;
    });
    /////////////////////////////////////////////////////

    // Context menu
    /////////////////////////////////////////////////////
    $("body").on("contextmenu", "#tableBody tbody tr", function(e) {
	e.preventDefault();
	if (!$(this).hasClass("selected")){
            $("#tableBody tbody tr.selected").removeClass("selected");
            $(this).addClass("selected");
	}

	var selected = $("#tableBody tbody tr.selected");
	if (selected.length > 1){
            $("#contextInfo").addClass("disabled");
            $("#contextCopy").addClass("disabled");
            $("#contextCopy span").removeClass("text-primary");
	}
	else{
            $("#contextCopy span").addClass("text-primary");
            $("#contextmenu ul li.disabled").removeClass("disabled")
	}

	var ids = [];
	var table = $("#tableBody").DataTable();
	selected.each(function() {
            ids.push(table.cell($(this), $("td.rowid", this)).data());
	});

	var contextmenu = $("#contextmenu");
	contextmenu.prop("ids", ids);
	contextmenu.css({left: e.pageX,
			 top: e.pageY});
	contextmenu.show();
    });

    $("html").click(function(e) {
	$("#contextmenu").hide();
    });

    /////////////////////////////////////////////////////

    // Context buttons
    /////////////////////////////////////////////////////
    $("#contextInfo").click(function() {
	if ($(this).hasClass("disabled")){ return false; }
	$.fancybox({
            type: "ajax",
            href: "/requests/" + $("#contextmenu").prop("ids")
	});
    });

    $("#contextEdit").click(function() {
	if ($(this).hasClass("disabled")){ return false; }
	alert("Edit");
	$.fancybox({
            type: "iframe",
            href: "/editrequest.html",
            title: "Edit Request"
	});
    });

    $("#contextCopy").click(function() {
	if ($(this).hasClass("disabled")){ return false; }
	alert("COPY");
    });

    $("#contextApprove").click(function() {
	if ($(this).hasClass("disabled")){ return false; }
	var ajax_calls = [];
	var ids = $("#contextmenu").prop("ids");
	for(var i in ids) {
            ajax_calls.push($.ajax({url: "/requests/" + ids[i],
                                    type: "PUT",
                                    data: {"status": "Approved"}}));
	}
	$.when.apply(this, ajax_calls).done(function() {
            $("#tableBody").DataTable().ajax.reload();
            bootstrap_alert("Info!", "Approved " + ids.length + " request(s)", "alert-info");
	});
    });

    $("#contextDelete").click(function() {
	if ($(this).hasClass("disabled")){ return false; }
	var ajax_calls = [];
	var ids = $("#contextmenu").prop("ids");
	for(var i in ids) {
            ajax_calls.push($.ajax({url: "/requests/" + ids[i],
                                    type: "DELETE"}));
	}
	$.when.apply(this, ajax_calls).done(function() {
            $("#tableBody").DataTable().ajax.reload();
            bootstrap_alert("Attention!", "Deleted "+ ids.length +" request(s)", "alert-danger");
	});
    });
    /////////////////////////////////////////////////////

    // Pressing Delete key
    /////////////////////////////////////////////////////
    $("body").keypress(function(e) {
	if (e.keyCode == 46){  //delete key
            var selected = $("#tableBody tbody tr.selected");
            if (!selected.length){ return; }
            bootbox.confirm("Really delete " + selected.length + " request(s)?", function(result) {
		if (!result){ return; }
		var ajax_calls = []
		var table = $("#tableBody").DataTable();
		selected.each(function() {
		    var id = table.cell($(this), $("td.rowid", this)).data();
		    ajax_calls.push($.ajax({url: "/requests/" + id,
					    type: "DELETE"}));
		});
		$.when.apply(this, ajax_calls).done(function() {
		    table.ajax.reload();
		    bootstrap_alert("Attention!", "Deleted " + ajax_calls.length + " requests" , "alert-danger");
		});
            });
	}
    });
    /////////////////////////////////////////////////////


    // floating alertbox
    /////////////////////////////////////////////////////
    bootstrap_alert = function(status, message, level){
        // the below pops the notification into existence immediately
        // hence we add the hide to allow fadeIn once filled with html
        $("#notification").hide().html(`
            <div class='alert alert-dismissible ###LEVEL###' role='alert'>
                <button type='button' class='close' data-dismiss='alert'>
                    <span class='glyphicon glyphicon-remove-sign'></span>
                </button>
                <strong>###STATUS###</strong> ###MESSAGE###\
            </div>`.replace("###LEVEL###", level)
                   .replace("###MESSAGE###", message)
                   .replace("###STATUS###", status));
        $("#notification").fadeIn("slow").delay(2000).fadeOut("slow");
    };
});

