import json
from pathlib import Path
from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db
from app.analysis import SocialNetworkAnalyzer
from app.models import Entity

def main():
    # 1. Init DB (Ensure tables exist)
    # init_db() # Assuming DB is already populated from Module 2
    
    db = SessionLocal()
    
    try:
        print("Initializing Social Network Analyzer...")
        analyzer = SocialNetworkAnalyzer(db)
        
        print("Building graph from database relations...")
        analyzer.build_graph()
        
        print(f"Graph stats: {analyzer.graph.number_of_nodes()} nodes, {analyzer.graph.number_of_edges()} edges")
        
        print("Analyzing power structure and social stratification...")
        results = analyzer.analyze_power_structure()
        
        # Print some interesting findings
        print("\n=== Key Figures Discovered ===")
        sorted_nodes = sorted(results.items(), key=lambda x: x[1]['betweenness'], reverse=True)
        for node_id, data in sorted_nodes[:5]:
            print(f"Name: {data['name']}")
            print(f"  Role: {data['inferred_role']}")
            print(f"  Betweenness: {data['betweenness']:.4f}")
            print(f"  Tags: {', '.join(data['tags'])}")
            print("-" * 30)
            
        print("\n=== Exporting Visualization Data ===")
        echarts_data = analyzer.export_echarts_json(results)
        
        # Determine base directory (project root: land_deed_system)
        base_dir = Path(__file__).resolve().parent.parent
        
        output_dir = base_dir.parent / "output"
        if not output_dir.exists():
             output_dir = base_dir / "output"
             
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "social_network_graph.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(echarts_data, f, ensure_ascii=False, indent=2)
            
        print(f"Graph data saved to {output_file}")
        print("You can now visualize this JSON using Apache ECharts.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
