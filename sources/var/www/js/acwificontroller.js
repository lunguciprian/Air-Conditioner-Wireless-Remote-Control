
////////////////////////////////////////////////////////////////////////////////
//                                                                            //
//                                Global Vars                                 //
//                                                                            //
////////////////////////////////////////////////////////////////////////////////


var payload = {};
    payload['state'] = 'on';
	payload['fan'] = '0';
	payload['temp'] = '24';
/*
var state = 'on';
var temp = 24;
var fan = 0;
*/
var loc = window.location;
var webSocket = 'ws:';
var webService = 'http:';

webSocket += "//" + loc.host; webSocket += ":9001/";
webService += "//" + loc.host; webService += ":8080/acwificontroller";

console.log(loc.host);

var ws = new WebSocket(webSocket);
window.onfocus = function () { 
	console.log("focus") 
	getInfo();
};

/*
window.onblur  = function () { 
	console.log("onblur") 
	ws.close();
};
*/

$(document).ready(function(){

	$.ajaxSetup({
	  	beforeSend: function() {
	  		console.log("beforeSend");
	     	$('.panel-body').addClass('disabled');
	     	$('#state').addClass('spinner');
	  	},
	  	complete: function(){
			$('.panel-body').removeClass('disabled');
	     	$('#state').removeClass('spinner');
	  	},
	  	success: function() {}
	});


	$('#password').on('input',function(e){
		
		$('#login').prop( "disabled", ($('#password').val().length > 0) ? false : true );

    });

    $('#login').on('click', function(){

		requestLogin($('#password').val());

	});

    $('#state').on('click', function(){

		if($(this).val() == 'on'){
			$(this).val('off');
		} else if($(this).val() == 'off'){
			$(this).val('on');
		}

    	payload['state'] = $(this).val();
		putInfo();
    });

    $('#fan .btn').on('click', function(){

    	payload['state'] = 'on';
        payload['fan'] = $(this).val();
		putInfo();

    });

    $('ul.pagination li').on('click', function(){

    	payload['state'] = 'on';
        payload['temp'] = $(this).val();
		putInfo();

    });

	initWebSocketClient();
	getInfo();
});

function putInfo(value){

	var backend = [webService, 'hvacrtcu'].join('/');

	$.ajax({
		url: backend.toLowerCase(),
		type: "PUT",
		data:JSON.stringify(payload),
		success: function (data) {

			console.log( "success"+ data );
		},
		error: function (result) {

			console.log( "Error"+ result );

		}
	});

}

function getInfo() {

    var backend = [webService, "hvacrtcu"].join('/');

    $.ajax({
        url: backend.toLowerCase(),
        type: "GET",
        success: function (data) {

            var response = jQuery.parseJSON(data);

            if(response.hasOwnProperty('state') && response.hasOwnProperty('fan') && response.hasOwnProperty('temp')){

				payload['state'] = response['state'];
				payload['fan'] = response['fan'];
				payload['temp'] = response['temp']['target'];

            	updateStateButton(response['state']);
            	updateNowTemperature(response['temp']['now']);
            	updateTargetTemperature(response['state'], response['temp']['target']);
            	updateFan(response['state'], response['fan'])

            } else {

                console.log("Response not valid" + data);

            }

        },
        error: function (result) {

            console.log( "Error"+ result );

        }
    });

}


function updateStateButton(value){

	$('#state').val(value);

	if(value == 'on'){
		$('#state .glyphicon').removeClass('state-on');
        $('#state .glyphicon').addClass('state-off');
	} else if(value == 'off'){
		$('#state .glyphicon').removeClass('state-off');
        $('#state .glyphicon').addClass('state-on');
	}

}

function updateNowTemperature(value){

	$("#now").html("NOW: "+ value +" &#8451;");
	$("#now").removeClass('label-info');
	$("#now").removeClass('label-warning');
	$("#now").removeClass('label-danger');
	$("#now").removeClass('label-default');

	if(value <= 26){
		$("#now").addClass('label-info');
	} else if(value < 27){
		$("#now").addClass('label-warning');
	} else {
		$("#now").addClass('label-danger');
	}

}

function updateTargetTemperature(state, temperature){

    $('ul.pagination li').each(function(i, obj){
        $(obj).removeClass('active');
    });

	if(state == 'on'){

		$('ul.pagination li').each(function(){
			if($(this).val() == temperature){
				$(this).addClass('active');
			}
		});
	}
}

function updateFan(state, fan){

    $('#fan .btn').siblings().removeClass('active');
	if(state == 'on'){
		$('#fan .btn').each(function(){
			if($(this).val() == fan){
				$(this).addClass('active');
			}
		});
	}
}

function enableUIContent(){

	$('#auth').addClass('hidden');
	$('#content').removeClass('disabled');

}

function requestLogin(value){

	var backend = [webService, 'login', value].join('/');

	$.ajax({
		url: backend.toLowerCase(),
		type: "GET",
		success: function (data) {

			if (data == "True"){
				
				enableUIContent();
				
			} else {
				
				$('#password').val("");
			
			}

		},
		error: function (result) {

			console.log( "Error"+ result );

		}
	});
}

///////////////////////////////////////////////////////////////////////////////////////////
//                                                                                       //
//                                     WEBSOCKET SECTION                                 //
//                                                                                       //
///////////////////////////////////////////////////////////////////////////////////////////

// ws.send(input.value);
function initWebSocketClient() {

    
    ("WebSocket" in window) ? console.log("WebSocket is supported by your Browser!") : console.log("WebSocket NOT supported by your Browser!");

    // Connect to Web Socket
    ws = new WebSocket(webSocket);

    // Set event handlers.
    ws.onopen = function() {
        console.log("WebSocket open");
    };

    ws.onmessage = function(e) {

        // e.data contains received string.
        var response = jQuery.parseJSON(e.data);

		console.log(e.data)

        if(response.hasOwnProperty('state') && response.hasOwnProperty('fan') && response.hasOwnProperty('temp')){

			payload['state'] = response['state'];
			payload['fan'] = response['fan'];
			payload['temp'] = response['temp']['target'];

        	updateStateButton(response['state']);
        	updateNowTemperature(response['temp']['now']);
        	updateTargetTemperature(response['state'], response['temp']['target']);
        	updateFan(response['state'], response['fan'])

        }

    };
 
    ws.onerror = function(e) {
        console.log("onerror");
        console.log(e)
    };

    ws.onclose = function() {
        console.log("onclose");
    };
}
