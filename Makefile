build:
	docker build -t gigi -f Dockerfile .

run:
	docker compose up --build

down:
	docker compose down -v