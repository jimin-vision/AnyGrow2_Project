/* -----------------------------------------------------------------

anygrow2_server.js
웹서버를 구동하며, 애니그로우 디바이스와 WebApp 사이에서 데이터를 처리하는 파일입니다. 

----------------------------------------------------------------- */


// 해당 프로그램에 활용되는 모듈 추출
const http = require('http'); 				// 웹서버 실행을 위한 node 내장 모듈
const url = require('url');
const fs = require('fs');
const socketio = require('socket.io');		// 소켓통신을 위한 외부 모듈. npm 설치 필요
const SerialPort = require('serialport').SerialPort;		// 시리얼 통신을 위한 외부 모듈. npm 설치 필요



// 애니그로우와 웹서버의 시리얼통신을 위하여, 시리얼포트 객체 생성
const serialPort = new SerialPort({path:"COM5",	// ***디바이스 연결 후, 'COM#' 포트번호 반영 필요 	
	baudRate: 38400,
	dataBits: 8, 
        parity: 'none', 
        stopBits: 1
}, false); 



// 활용 변수 생성 및 초기화
var packetLED='';
var reciving_data='';
	
var rq_state='';
var rc_state='ok';
var receive_count=0;

var data_state='';



// 다른 디바이스에서 해당 WebApp에 접속할 수 있도록, 웹서버 생성 및 실행
var server = http.createServer(function (request, response) {

	var pathname = (url.parse(request.url).path).substr(1);
	console.log(pathname);
	
	if(pathname == ''){
		// index.html 파일 읽기
		fs.readFile('index.html', function (error, data) {
			response.writeHead(200, { 'Content-Type': 'text/html' });
			response.end(data);
		});
	}
	else{
		// 나머지 파일들 확장자별로 나눠서 읽기
		fs.readFile(pathname, function (error, data) {
			if(pathname.match('.html'))
				response.writeHead(200, { 'Content-Type': 'text/html'});
			
			else if(pathname.match('.js'))
				response.writeHead(200, { 'Content-Type': 'application/javascript' });
					
			else if(pathname.match('.css'))
				response.writeHead(200, { 'Content-Type': 'text/css' });	
			response.end(data);
		});
	}

}).listen(52273); 	// 웹서버 접속 포트번호



// 웹서버와 index.html의 소켓통신을 위하여, 소켓 생성 및 실행
const io = socketio.listen(server);

io.sockets.on('connection', function (socket) {
	
	console.log('Socket on');

	socket.on('serial_write', function (data) {	//serial_write 이벤트
		rq_state=data;
	});
	
	socket.on('comm_state', function (data) {
		data_state = "sensor data response";
		rc_state='ok';	// 센서 데이터 수신 중 LED 제어 요청이 들어올 경우, 수신 완료 후 요청 진행 
	});
	
});


// 센서 데이터를 실시간으로 확인하고, LED 제어 패킷을 보내기 위해, 1초 주기로 인터벌 세팅
setInterval(function(){
	
	console.log(rq_state);
	
	if(rc_state=='ok'){	
		
		// Buffer 사이즈 30으로 초기화
		packetLED = Buffer.alloc(30);
		
		// index.html에서 LED 제어 버튼 클릭 시, 해당 패킷데이터로 세팅 및 디바이스로 전송
		if(rq_state!=''){
			if(rq_state=='Off')			// LED OFF
				packetLED = Buffer.from("0201FF4CFF00FF00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03", "hex");
			else if(rq_state=='Mood')	// LED 무드등 모드로 ON
				packetLED = Buffer.from("0201FF4CFF00FF02FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03", "hex");
			else if(rq_state=='On')		// LED 전체 ON
				packetLED = Buffer.from("0201FF4CFF00FF01FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03", "hex");

			console.log("@@@@@@@@@@ LED 제어 패킷 전송 @@@@@@@@@@");
			console.log(packetLED);
			serialPort.write(packetLED);	// LED 제어 패킷데이터 시리얼통신을 통해 디바이스로 전송
			rq_state='';					 
		}	
	
		// 센서데이터 요청
		packetLED = Buffer.from("0202FF53FF00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03", "hex");
		console.log("////////// 모니터링 센서데이터 요청 //////////");
		//console.log(packetLED);
		serialPort.write(packetLED);		// 센서데이터 요청 패킷데이터 시리얼통신을 통해 디바이스로 전송
		rc_state='wait';					
	}
	else{	// 데이터 유실되었을 때, 5초 기다린 후 센서 데이터 재요청
		receive_count++;

		if(receive_count>5){				
			rc_state='ok';
			receive_count=0;
		}
	}
	
}, 1000);	// 1초 주기



// 애니그로우와 웹서버의 시리얼통신을 위하여, 시리얼포트 실행
serialPort.open(function () {

	console.log('SerialPort open');

	serialPort.on('data', function(data) {
		
		// 애니그로우로부터 모니터링 센서 데이터 수신
		reciving_data = data;				
		console.log(" - 센서데이터 수신");
		console.log(reciving_data);

		
		// 수신된 센서 데이터를 index.html으로 전달하기 위해 데이터 타입 변환 
		var reciving_data_hex = reciving_data.toString('hex');
		var arr_reciveData='';

        for(i=0;i<reciving_data_hex.length;i++){
            if((i%2)==0&& i!=0){
                arr_reciveData = arr_reciveData+',';
            }
            arr_reciveData = arr_reciveData+reciving_data_hex.substring(i,i+1);
		}
		//console.log(arr_reciveData);
		
		
		// 소켓통신으로 index.html에 센서 데이터 전달
		io.sockets.emit('serial_recive',arr_reciveData);
		
		
	});

	// 시리얼포트에 문제가 생길 경우, 에러 출력
	serialPort.write("ls\n", function(err, results) {
		console.log('err ' + err);
		console.log('results ' + results);
	});
});

