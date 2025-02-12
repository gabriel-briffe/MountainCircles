import os

def normJoin(*args):
    return os.path.normpath(os.path.join(*args))