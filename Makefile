build:
	docker build -t gigi -f Dockerfile .

run:
	docker compose up --build

down:
	docker compose down -v

stress:
	k6 run stress-test/rinha.js

hr:
	docker compose down -v
	docker build -t gigi -f Dockerfile .
	docker compose up --build
