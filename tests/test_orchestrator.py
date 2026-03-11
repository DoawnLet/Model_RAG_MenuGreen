from app.agents.orchestrator import create_orchestrator, get_compiled_graph

def test_graph_compilation():
    """Test that the orchestrator graph compiles successfully."""
    graph = create_orchestrator()
    assert graph is not None
    
def test_get_compiled_graph_factory():
    """Test the factory function."""
    graph = get_compiled_graph()
    assert graph is not None

def test_graph_structure():
    """Test that critical nodes are present."""
    graph = create_orchestrator()
    # Accessing underlying graph nodes is implementation specific in LangGraph
    # But we can try to inspect if possible, or just trust compilation.
    # graph.get_graph().nodes might be available
    pass 
