build:
	docker build -t gigi -f Dockerfile .

compose:
	docker compose up --build

down:
	docker compose down -v