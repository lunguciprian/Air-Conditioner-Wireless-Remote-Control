
////////////////////////////////////////////////////////////////////////////////
//                                                                            //
//                                Global Vars                                 //
//                                                                            //
////////////////////////////////////////////////////////////////////////////////
var temp = 24;
var fan = 0;

var loc = window.location;
var webSocket = 'ws:';
var webService = 'http:';

webSocket += "//" + loc.host; webSocket += ":9001/";
webService += "//" + loc.host; webService += ":8080/acwificontroller";

$(document).ready(function(){

    initWebSocketClient();
    getStoredValues();
    getCurrentTemparature();

	$('#password').on('input',function(e){
		
		$('#login').prop( "disabled", ($('#password').val().length > 0) ? false : true );

    });

    $('#login').on('click', function(){
		requestLogin($('#password').val());
	});

    $('#state').on('click', function(){

		if($(this).val() == 'on'){
			updateStateButton('off');
		} else if($(this).val() == 'off'){
			updateStateButton('on');
		}

        sendAction($(this).val());
    });

    $('#fan .btn').on('click', function(){
        $(this).siblings().removeClass('active');
        $(this).addClass('active');
        fan = $(this).val();

        sendIRPulse();
    });

    $('ul.pagination li').on('click', function(){

        $('ul.pagination li').each(function(i, obj){
            $(obj).removeClass('active');
        });

        $(this).addClass('active');
        temp = $(this).val();

        sendIRPulse();
    });
});

function updateStateButton(value){

	console.log(value);

	$('#state').val(value);

	if(value == 'on'){
		$('#state .glyphicon').removeClass('state-off');
        $('#state .glyphicon').addClass('state-on');
	} else if(value == 'off'){
		$('#state .glyphicon').removeClass('state-on');
        $('#state .glyphicon').addClass('state-off');
	}

}

function updateTemperature(value){

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
	
function updateButtons(state, fan, temperature){

	updateStateButton(state);
	
	$('#fan .btn').siblings().removeClass('active');
	$('ul.pagination li').siblings().removeClass('active');

	if(state == 'on'){
		$('#fan .btn').each(function(){
			if($(this).val() == fan){
				$(this).addClass('active');
			}
		});

		$('ul.pagination li').each(function(){
			if($(this).val() == temperature){
				$(this).addClass('active');
			}
		});
	}
}

function getCurrentTemparature(){

    var backend = [webService, 'temperature'].join('/');

    $.ajax({
        url: backend.toLowerCase(),
        type: "GET",
        success: function (data) {

			updateTemperature(data);

        },
        error: function (result) {

            console.log( "Error"+ result );

        }
    });
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

function sendAction(value){

	if(value == 'on'){
		sendIRPulse();
	}
	else {

		var backend = [webService, 'action', value].join('/');

		$.ajax({
			url: backend.toLowerCase(),
			type: "GET",
			success: function (data) {

				console.log( "success"+ data );
			},
			error: function (result) {

				console.log( "Error"+ result );
			}
		});
	}
}

function getStoredValues(){

    var backend = [webService, "status"].join('/');

    $.ajax({
        url: backend.toLowerCase(),
        type: "GET",
        success: function (data) {

            var response = jQuery.parseJSON(data);

            if(response.hasOwnProperty('state') && response.hasOwnProperty('fan') && response.hasOwnProperty('temperature')){

				updateButtons(response['state'], response['fan'], response['temperature']);

            } else {

                console.log("Response not valid" + data);

            }

        },
        error: function (result) {

            console.log( "Error"+ result );

        }
    });
}

function sendIRPulse(){

    var backend = [webService, temp, fan].join('/');

    $.ajax({
        url: backend.toLowerCase(),
        type: "POST",
        cache: false,
        contentType: false,
        processData: false,
        data: false,
        success: function (data) {

            console.log( "success"+ data );

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
    var ws = new WebSocket(webSocket);

    // Set event handlers.
    ws.onopen = function() {
        console.log("WebSocket open");
    };

    ws.onmessage = function(e) {

        // e.data contains received string.
        var response = jQuery.parseJSON(e.data);

		console.log(e.data)

		if(response.hasOwnProperty('returncode') && response['returncode'] == 0){
			if(response.hasOwnProperty('temperature')){

				updateTemperature(response['temperature']);

			}

		// de refacut, toate trebuie sa contina returncode
		} else if(response.hasOwnProperty('state') && response.hasOwnProperty('fan') && response.hasOwnProperty('temperature')){

				updateButtons(response['state'], response['fan'], response['temperature']);

		}

    };
 
    ws.onerror = function(e) {
        console.log("onerror");
        console.log(e)
    };
}
