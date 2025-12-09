/* -----------------------------------------------------------------

anygrow2_client.js
사용자 페이지에서 웹서버로 데이터를 주고 받기 위한 스크립트 파일입니다. 

----------------------------------------------------------------- */

			// 활용 변수 생성
			var packet ='';									// 수신 패킷데이터 저장
			var ETX='ff,ff'; 								// 03';  패킷의 끝을 알림

			var arrEnv = new Array(4);						// 환경정보 값 2차원 배열에 저장
			for(var i=0; i<5; i++)							// [0][ ]:온도	[1][ ]:습도	[2][ ]:CO2	[3][ ]:조도
				arrEnv[i] = new Array(5);					// [ ][0]:센서값	[ ][1]:최소값	[ ][2]:최대값	[ ][3]:알람플래그
			
			var val_max = new Array(35, 90, 4999, 8000);	// 환경정보 최대값 정의 (모니터링 화면 내 차트, 알람 임계값으로 활용)
		
	
			
			// 페이지가 로드 되면 자동으로 실행되는 함수
			window.onload = function () {
				
				// 알림값 초기화
				chanage_threshold();
				alram_init();
			
				// 화면 스크린에 따라 모니터링 그래프 사이즈 정의 
			    var bar_height = screen.height*0.35;
				var bar_width = (screen.width/8)-25;
				$('#chart_temperature, #chart_humidity, #chart_co2, #chart_illumination').css("width",(bar_width)+"px");
		
				// 소켓 생성	
                var socket = io.connect();	
				
				
				// LED 제어를 위해, 버튼 선택 시 소켓통신을 통해 웹서버로 해당 시그널 전송 
				document.getElementById('btnOff').onclick = function(){	
					socket.emit('serial_write', "Off");		// LED OFF
				}
				document.getElementById('btnMood').onclick = function(){	
					socket.emit('serial_write', "Mood");	// LED 무드등 모드로 ON	
				}
				document.getElementById('btnOn').onclick = function(){	
					socket.emit('serial_write', "On");		// LED 전체 ON
				}

				

				// 센서 데이터 모니터링을 위해, 소켓통신을 통해 웹서버로 해당 시그널 수신
                socket.on('serial_recive', function (data) {
					
					// 패킷이 끊어서 들어오는 경우가 있어, 패킷의 끝을 알리는 ETX가 들어올때까지 값 계속 더해줌
					packet += data;
					console.log(packet);

					// ETX가 들어오면 패킷이 완성 / 작업 시작
					if(packet.match(ETX)){
					
						// 정상적으로 패킷 수신했음을 서버쪽에 알림
						socket.emit('comm_state', "sensor data response");	
					    
						// 수신 패킷을 "," 기준으로 잘라서, 배열로 저장
					    arr_reciveData =packet.toString('utf8').split(',');
						
					    //var modePacket = arr_reciveData[1];
					    
						// 길이를 통해, 패킷이 정상적으로 도착했는지 확인
					    if(arr_reciveData.length==30){

							// MODE 패킷을 통해, 센서에서 전달된 데이터인지 확인
					        if(arr_reciveData[1]=="02"){
					            // 센서에서 전달된 패킷 데이터를 실제 사용할 수 있도록 가공
					            arrEnv[0][0] = hex2dec(arr_reciveData,10,12)/10;	// 온도
								arrEnv[1][0] = hex2dec(arr_reciveData,14,16)/10;	// 습도
								arrEnv[2][0] = hex2dec(arr_reciveData,18,21);		// CO2
								arrEnv[3][0] = hex2dec(arr_reciveData,23,26);		// 조도
    					    }
      
    					    // 모니터링 탭 화면에 현재 센서값을 텍스트형태로 출력
					        $('#label_temperature').text(String(arrEnv[0][0]));	
						    $('#label_humidity').text(String(arrEnv[1][0]));
							if(arrEnv[2][0]<6000)	
							    $('#label_co2').text(String(arrEnv[2][0]));	
						    $('#label_illumination').text(String(arrEnv[3][0]));
							
							
							// 센서값이 임계값을 벗어난 경우, 알람 메시지창 노출
							alram(arrEnv[0][0], arrEnv[0][1], arrEnv[0][2], arrEnv[0][3],"온도");
							alram(arrEnv[1][0], arrEnv[1][1], arrEnv[1][2], arrEnv[1][3], "습도");
							if(arrEnv[2][0]<6000)	
								alram(arrEnv[2][0], arrEnv[2][1], arrEnv[2][2], arrEnv[2][3], "이산화탄소");
							alram(arrEnv[3][0], arrEnv[3][1], arrEnv[3][2], arrEnv[3][3],"조도");
							
					    
						    // 윈도우 사이즈에 따라 차트 사이즈 조절
						    $('#chart_temperature').css("height",(arrEnv[0][0]/val_max[0]*bar_height)+"px");
						    $('#chart_humidity').css("height",(arrEnv[1][0]/val_max[1]*bar_height)+"px");
							if(arrEnv[2][0]<6000)
							    $('#chart_co2').css("height",(arrEnv[2][0]/val_max[2]*bar_height)+"px");
						    $('#chart_illumination').css("height",(arrEnv[3][0]/val_max[3]*bar_height)+"px");
					   	}
					}
					packet ='';	
                });
			}
			
			
			// 16진수로 들어온 센서 패킷데이터를 실제 활용할 수 있도록 정수로 변환하는 함수 (AnyGrow 프로토콜.xlsx 참고)
			function hex2dec(arr, first, last){	
			  
			    
			    var area = last-first;
			    result = '';
			    
			   for(var i=first; i<=last; i++){
			        result += String(eval(arr[i])-30);
			    }
			    
			    return eval(result);
			}
			
			// 센서값이 임계값을 벗어난 경우, 알람 메시지창 노출하는 함수
			function alram(val_data, val_min, val_max, alram_flag, factor){
				var comment='';
				if(alram_flag==0){
					if(val_data<val_min){
						comment = factor+"가 너무 낮습니다";
						
						alert(comment);
						$('#alram_comment').text(comment);	
						
					}
					else if(val_data>val_max){
						comment = factor+"가 너무 높습니다";
						
						alert(comment);
						$('#alram_comment').text(comment);	
					}
					else{
						comment='';
						$('#alram_comment').text(comment);	
					}
				}
				alram_flag=1;

			}
			
			// 임계값 설정 함수 (초기화, setting탭에서 게이지 변경 시 활용)
			function chanage_threshold(){
				arrEnv[0][1] = document.getElementById('tf_temperature_min').value;
				arrEnv[0][2] = document.getElementById('tf_temperature_max').value;
				arrEnv[1][1] = document.getElementById('tf_humidity_min').value;
				arrEnv[1][2] = document.getElementById('tf_humidity_max').value;
				arrEnv[2][1] = document.getElementById('tf_co2_min').value;
				arrEnv[2][2] = document.getElementById('tf_co2_max').value;
				arrEnv[3][1] = document.getElementById('tf_illumination_min').value;
				arrEnv[3][2] = document.getElementById('tf_illumination_max').value;
			}
		
			// 알람 플래그 초기화 함수
			function alram_init(){
				arrEnv[0][3] = 0;
				arrEnv[1][3] = 0;
				arrEnv[2][3] = 0;
				arrEnv[3][3] = 0;
			}