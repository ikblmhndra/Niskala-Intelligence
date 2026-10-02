# Jalan pintas operasional. Detail: README.md dan docs/CUTOVER_RUNBOOK.md.
.PHONY: help fresh-deploy fresh-status

help:
	@echo "make fresh-deploy [ARGS='--skip-build --skip-nginx']  deploy dari nol di host ini (idempoten)"
	@echo "make fresh-status                                     status container stack"

fresh-deploy:
	bash tools/ops/fresh_deploy.sh $(ARGS)

fresh-status:
	docker compose --env-file docker/stack.env --profile app ps
