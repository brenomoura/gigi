build:
	docker build -t gigi -f Dockerfile .

run:
	docker compose up --build

down:
	docker compose down -v

stress:
	k6 run stress-test/rinha.js