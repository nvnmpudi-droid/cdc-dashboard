import argparse
import sys
from dataset_config import get_default_config
from database_init import initialize_osis_db
from analysis import run_logic_audit
from forecast_agent import run_forecast_agent

def run_pipeline(config=None, skip_db=False, use_llm=True):
    if config is None:
        config = get_default_config()
    print("="*55)
    print("  OSIS Pipeline v2.0")
    print("="*55)
    print(f"  Dataset: {config.source_label}")
    print(f"  Domain : {config.domain}")
    print(f"  Metric : {config.metric_name}")
    print(f"  Entity : {config.entity_filter}")
    print("="*55)
    if not skip_db:
        print("\nSTEP 1 -- Data Ingestion")
        config = initialize_osis_db(config)
        if config is None:
            print("Ingestion failed"); sys.exit(1)
    else:
        print("\nSTEP 1 -- Skipped")
    print("\nSTEP 2 -- Logic Agent")
    fact_packet = run_logic_audit(config=config, export_json=True)
    if fact_packet.get("status") != "success":
        print(f"Logic Agent failed: {fact_packet.get('message')}"); sys.exit(1)
    print("\nSTEP 3 -- Inference Agent")
    try:
        import requests
        requests.get("http://127.0.0.1:11434/", timeout=3)
        llm_available = True
    except Exception:
        llm_available = False
    if use_llm and llm_available:
        from summarization import generate_strategic_brief
        generate_strategic_brief(input_file="logic_output.json", export=True)
    else:
        print("  Ollama unavailable -- deterministic brief only")
    print("\nSTEP 4 -- Forecast Agent")
    run_forecast_agent(config=config)
    
    print("\nSTEP 5 -- Chanakya Layer (Mimamsa Minister)")
    from chanakya_agent import run_chanakya_agent
    run_chanakya_agent(config=config)
    print("\nOSIS Pipeline Complete")
    print("  logic_output.json    -> LogicAgent Fact Packet")
    print("  strategic_brief.txt  -> Governed Strategic Brief")
    print("  forecast_output.json -> Prophet Forecast")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-db", action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    args = parser.parse_args()
    run_pipeline(config=get_default_config(), skip_db=args.skip_db, use_llm=not args.no_llm)
