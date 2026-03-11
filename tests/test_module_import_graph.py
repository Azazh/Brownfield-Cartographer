import unittest
from src.graph.module_import_graph import ModuleImportGraph


class TestModuleImportGraph(unittest.TestCase):
    def test_graph_add_and_pagerank(self):
        try:
            g = ModuleImportGraph()
            g.add_module('a.py')
            g.add_module('b.py')
            g.add_import('a.py', 'b.py')
            pr = g.pagerank()
            self.assertIn('a.py', pr)
            self.assertIn('b.py', pr)
        except Exception as e:
            import traceback
            print("[TestModuleImportGraph] Exception in test_graph_add_and_pagerank:")
            traceback.print_exc()
            raise

    def test_strongly_connected_components(self):
        try:
            g = ModuleImportGraph()
            g.add_module('a.py')
            g.add_module('b.py')
            g.add_import('a.py', 'b.py')
            g.add_import('b.py', 'a.py')
            scc = g.strongly_connected_components()
            self.assertTrue(any({'a.py', 'b.py'} == set(comp) for comp in scc))
        except Exception as e:
            import traceback
            print("[TestModuleImportGraph] Exception in test_strongly_connected_components:")
            traceback.print_exc()
            raise

if __name__ == "__main__":
    unittest.main()
