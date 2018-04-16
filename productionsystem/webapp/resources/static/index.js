$(document).ready(function() {

    function formatprogress(parametricjob){
        var striped = parametricjob.num_running + parametricjob.num_submitted > 0? "progress-bar-striped active": "";
        var percent_completed = 100 * parametricjob.num_completed / parametricjob.num_jobs;
        var percent_failed = 100 * parametricjob.num_failed / parametricjob.num_jobs;
        var percent_running = 100 * parametricjob.num_running / parametricjob.num_jobs;
        var percent_submitted = 100 * parametricjob.num_submitted / parametricjob.num_jobs;
        var num_other = parametricjob.num_jobs - (parametricjob.num_submitted + parametricjob.num_running + parametricjob.num_completed + parametricjob.num_failed)
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

    function refresh_table(){
      $.ajax({
        url: "/requests",
        type: "GET",
        cache: true,
        dataType: "json",
        error: function(request, status, error){
          console.warn(`Error getting table data!\nstatus: ${status}\nerror: ${error}\nrequest: ` + JSON.stringify(request));
          bootstrap_alert("Attention!", `Error getting table data! status: ${status} error: ${error}`, "alert-danger");
        },
        statusCode: {
          404: function(){
            console.warn(`404: Not Found when getting requests`)
            bootstrap_alert("Attention!", `404: Not Found when getting requests`, "alert-warning");
          }
        },
        success: function(response, status, request){
          columns = [{data: null,
                      width: '20px',
                      defaultContent: "<span class='glyphicon glyphicon-plus-sign text-primary details-control' style='cursor:pointer'></span>",
                      orderable: false}]
          $("#tableBody").DataTable({data: response,
                                     bDestroy: true,
                                     autoWidth: false,
                                     order: JSON.parse(request.getResponseHeader('Datatable-Order')),
                                     columns: columns.concat(JSON.parse(request.getResponseHeader('Datatable-Columns'))),
                                     columnDefs: [{targets: "_all", className: "dt-body-left dt-head-left",
                                                   render: function(data, type, row, meta){
                                                     return type === 'display' && data.length > 40 ? data.substr( 0, 40 ) +'…' : data;
                                                   }}]
                                     })
        }
      });
    };

    function refresh_subtable(request_id){
        $.ajax({
            url: `/requests/${request_id}/parametricjobs`,
            type: "GET",
            cache: true,
            dataType: "json",
            error: function(request, status, error){
              console.warn(`Error getting subtable data!\nstatus: ${status}\nerror: ${error}\nrequest: ` + JSON.stringify(request));
              bootstrap_alert("Attention!", `Error getting subtable data! status: ${status} error: ${error}`, "alert-danger");
            },
            statusCode: {
              404: function(){
                console.warn(`404: Not Found when requesting parametricjobs for request '${request_id}'`)
                bootstrap_alert("Attention!", `404: Not Found when requesting parametricjobs for request '${request_id}'`, "alert-warning");
              },
              400: function(){
                console.warn(`Bad request! Request id '${request_id}' can probably not be cast to integer.`);
                bootstrap_alert("Attention!", `Bad request! Request id '${request_id}'`, "alert-danger");
              }
            },
            success: function(response, status, request){
              columns = [{data: null,
                          title: 'Progress',
                          width: '160px',
                          orderable: false},
                         {data: null,
                          width: '20px',
                          defaultContent: `<span class="glyphicon glyphicon-repeat text-primary reschedule" style="cursor:pointer" requestid="${request_id}"></span>`,
                          orderable: false}]
              $(`#subtable-${request_id}`).DataTable({data: response,
                                                      bDestroy: true,
                                                      autoWidth: false,
                                                      paging: false,
                                                      searching: false,
                                                      info: false,
                                                      order: JSON.parse(request.getResponseHeader('Datatable-Order')),
                                                      columns: JSON.parse(request.getResponseHeader('Datatable-Columns')).concat(columns),
                                                      columnDefs: [{"targets": -2,
                                                                    "render": function ( data, type, row, meta ) {
                                                                                return formatprogress(row);
                                                                              }
                                                                   },
                                                                   {"targets": -1,
                                                                    "render": function(data, type, row, meta){
                                                                                return row.status == 'Failed'? data: '';
                                                                               }
                                                                   }]
                                                      });
            }
        });
    };

    // Reload table ajax every 5 mins
    /////////////////////////////////////////////////////
    setInterval(refresh_table(), 300000);  // 5 mins


    // New request button
    /////////////////////////////////////////////////////
    $("#NewRequest").fancybox({
    	type: "iframe",
    	href: "/newrequest.html",
    	title: "Submit New Request"
    });
    /////////////////////////////////////////////////////

    // Admins button
    /////////////////////////////////////////////////////
    $("#Admins").fancybox({
    	type: "ajax",
    	href: "/admins",
    	title: "Admin Management",
    	afterClose: function(){refresh_table();}
    });
    /////////////////////////////////////////////////////

    // Reschedule macros
    /////////////////////////////////////////////////////
    $("#tableBody").on("click", "tbody tr td span.reschedule", function(){
	var subtable = $(this).closest("table").DataTable();
	var tr = $(this).closest("tr");
    var row = subtable.row(tr);
    var parametricjob_id = subtable.cell(row, $("td.rowid", tr)).data();
	var request_id = $(this).attr('requestid');
	console.log(`Rescheduling parametric job ${parametricjob_id} from request ${request_id}`)
	$.ajax({url: `requests/${request_id}/parametricjobs/${parametricjob_id}`,
		type: "PUT",
		data: {'reschedule': true},
		error: function(request, status, error){
		  console.warn(`Error rescheduling job!\nstatus: ${status}\nerror: ${error}\nrequest: ` + JSON.stringify(request));
		  bootstrap_alert("Attention!", `Error rescheduling job! status: ${status} error: ${error}`, "alert-danger");
		},
		success: function(){
		    console.log(`Parametric job ${parametricjob_id} from request ${request_id} successfully rescheduled.`)
		    bootstrap_alert("Success!", `Parametricjob '${parametricjob_id} rescheduled'`, "alert-success");
		    refresh_subtable(request_id);
		}});
    });

    // Request parametricjob subtable.
    /////////////////////////////////////////////////////
    $("#tableBody").on("click", "tbody tr td span.details-control", function() {
        var datatable = $("#tableBody").DataTable();
        var tr = $(this).closest("tr");
        var row = datatable.row(tr);
        var request_id = datatable.cell(row, $("td.rowid", tr)).data();
        $(this).toggleClass("glyphicon-plus-sign")
        $(this).toggleClass("glyphicon-minus-sign")
        $(this).toggleClass("text-primary")
        $(this).toggleClass("text-danger")
        if (row.child.isShown()){
            row.child.hide();
            return
        }
        row.child($("<table>", {id: `subtable-${request_id}`})).show()
        refresh_subtable(request_id);
    });

    /////////////////////////////////////////////////////

    // Double click a row
    /////////////////////////////////////////////////////
    $("#tableBody").on("dblclick", "tbody tr", function(e){
    	$.fancybox({
                type: "ajax",
                href: "/requests/" + $("#tableBody").DataTable().cell($(this), $("td.rowid", this)).data()
	    });
    });
    /////////////////////////////////////////////////////

    // Table row selection
    /////////////////////////////////////////////////////
    var last_selected = 0;
    $("#tableBody").on("click", "tbody tr", function(e){
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

