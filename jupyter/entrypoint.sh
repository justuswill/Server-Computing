#!/bin/bash
echo 'JUPYTER_STATUS=Running' >> ~/.bashrc
jupyter nbconvert --to=notebook --allow-errors --inplace --execute /scripts/$PY_FILE
echo 'JUPYTER_STATUS=Finished' >> ~/.bashrc
jupyter notebook /scripts/$PY_FILE --port=8888 --no-browser --ip=0.0.0.0 --allow-root
