#!/bin/sh
jupyter nbconvert --to=notebook --inplace --ExecutePreprocessor.enabled=True /scripts/$PY_FILE
jupyter notebook /scripts/$PY_FILE --port=8888 --no-browser --ip=0.0.0.0 --allow-root
