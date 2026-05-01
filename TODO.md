- slug대신에 문제 번호 기준 분류
- 유저 구분
- ui좀 koi랑 다르게
- 컴파일도 isolate안에서 할지, 매번 새로운 isolate열지 않고 그냥 파일 한번 지우는 식으로
- 맞았는지 틀렸는지 알려주는 정보 제한하기
- 체점 퍼센트 보여주기
  
isolate --box-id=0 --cg --processes=16 --env=PATH=/usr/bin:/bin --run -- /usr/bin/g++ -std=c++17 -O2 -pipe -o main main.cpp

--dir=/usr=/usr:ro
--dir=/lib=/lib:ro
--dir=/lib64=/lib64:ro

isolate --box-id=0 --cg --processes=16 --run -- /usr/bin/ls