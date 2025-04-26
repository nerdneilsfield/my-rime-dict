.PHONY: help
help:
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: clean
clean:
	rm -rf merged_text.txt

.PHONY: merge
merge:
	python scripts/merge_texts.py

.PHONY: compile
compile: