import networkx as nx


class JunoOntology:
    def __init__(self):
        self.graph = nx.DiGraph()
        self._initialize_base_ontology()

    def _initialize_base_ontology(self):
        nodes = [
            "Company",
            "Customer",
            "Product",
            "SalesOrder",
            "ProductionOrder",
            "Cost",
            "Revenue",
            "Margin",
            "Risk",
        ]
        for node in nodes:
            self.graph.add_node(node)

        relations = [
            ("Customer", "Product", "compra"),
            ("SalesOrder", "Revenue", "gera"),
            ("Product", "ProductionOrder", "gera"),
            ("ProductionOrder", "Cost", "consome"),
            ("Revenue", "Margin", "compõe"),
            ("Cost", "Margin", "compõe"),
            ("Margin", "Risk", "impacta"),
            ("Risk", "Action", "recomenda"),
        ]
        for src, dst, rel in relations:
            self.graph.add_edge(src, dst, relation=rel)

    def get_graph(self):
        return {
            "nodes": list(self.graph.nodes()),
            "edges": [
                {"source": u, "target": v, "relation": d["relation"]}
                for u, v, d in self.graph.edges(data=True)
            ],
        }

    def get_recommendation_logic(self, entity_type, entity_id):
        # Example logic: if margin is low, recommend action
        return "Analisar custos de produção e renegociar fornecedores de matéria-prima."
