"""shared loader for sdd script tests — imports the extension-less scripts
and the dashed hook filename via importlib."""
import importlib.util
import os
import sys
from importlib.machinery import SourceFileLoader

SDD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SDD)


def load_module(name, relpath):
    # explicit SourceFileLoader: spec_from_file_location cannot infer a
    # loader for extension-less files like `cost` and `quality`
    loader = SourceFileLoader(name, os.path.join(SDD, relpath))
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod
