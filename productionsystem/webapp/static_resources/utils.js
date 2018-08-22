function bootstrap_alert(level, status, message){
    var notification = $("#notification");
    var alert = $("<div>", {class: `alert alert-dismissible alert-${level} fade show shadow`, role: "alert"});
    var strong = $("<strong>");
    strong.text(status);
    var button = $("<button>", {type: "button", class: "close", "data-dismiss": "alert", "aria-label": "Close"});
    button.append($("<span/>", {class:"oi oi-circle-x", "aria-hidden": "true"}));
    alert.append(strong);
    alert.append("\t");
    alert.append(message);
    alert.append(button);
    notification.append(alert);
    alert.fadeIn("slow").delay(2000).fadeOut("slow", function(){alert.remove();});
};
