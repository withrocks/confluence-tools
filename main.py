#!/usr/bin/env python
import requests
import sys

class ConfluenceProvider:
    def __init__(user, passw):
        self.user = user
        self.passw = passw

    def get_diff_history(self, space):
        # Returns the diff history for a whole space
        pass


if len(sys.argv) < 4:
    print "Usage: <program> <base_url> <user> <pass>"
    sys.exit(1)

print sys.argv 
#provider = ConfluenceProvider(
