Execution:

cat secret-file | xargs -I{} ./main.py --url http://project.atlassian.net/wiki --user admin --pwd '{}'
