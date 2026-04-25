.PHONY: deploy start stop restart logs status

deploy:
	@bash deploy.sh

start:
	@sudo systemctl start repricer-web

stop:
	@sudo systemctl stop repricer-web

restart:
	@sudo systemctl restart repricer-web

logs:
	@sudo journalctl -u repricer-web -f

status:
	@sudo systemctl status repricer-web