#!/usr/bin/env python3

import asyncio
import sys
from registry import load_registry
from main import scrape_all

async def debug_test():
    print("=== DEBUG TEST ===")
    
    # Load registry
    companies = load_registry('registry.yaml')
    print(f"Loaded {len(companies)} companies")
    
    # Test only_ids filtering
    only_ids = ['dss']
    uniq_map = {c['id']: c for c in companies}
    
    if only_ids:
        subset = {}
        for oid in only_ids:
            if oid in uniq_map:
                subset[oid] = uniq_map[oid]
                print(f"Found company: {oid} - {uniq_map[oid]['Name']}")
            else:
                print(f"Company not found: {oid}")
        uniq = subset.values()
    else:
        uniq = uniq_map.values()
    
    print(f"Companies to process: {len(list(uniq))}")
    
    # Try scrape_all
    try:
        results = await scrape_all(registry_path='registry.yaml', notion_enabled=False, debug=True, only_ids=only_ids)
        print(f"Scrape results: {len(results)} companies")
        for result in results:
            print(f"  Company: {result.get('company')}, Events: {len(result.get('events', []))}")
    except Exception as e:
        print(f"Error in scrape_all: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(debug_test())
