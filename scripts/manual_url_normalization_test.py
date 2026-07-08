"""Test URL normalization for DuckDuckGo redirect URLs."""
import sys
sys.path.insert(0, 'i:/Project/voice2')

from services.agent_control.agent_memory import _normalize_url

# Test cases
test_urls = [
    ("//duckduckgo.com/l/?uddg=https%3A%2F%2Fapnews.com%2Farticle%2Ftrump-iran-war",
     "https://apnews.com/article/trump-iran-war"),
    
    ("//example.com/page",
     "https://example.com/page"),
    
    ("https://direct-url.com/article",
     "https://direct-url.com/article"),
    
    ("//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.reuters.com%2Fworld%2Fmiddle-east",
     "https://www.reuters.com/world/middle-east"),
]

print("Testing URL normalization:")
print("=" * 80)

all_passed = True
for input_url, expected in test_urls:
    result = _normalize_url(input_url)
    passed = result == expected
    all_passed = all_passed and passed
    
    status = "PASS" if passed else "FAIL"
    print(f"\n{status}")
    print(f"  Input:    {input_url}")
    print(f"  Expected: {expected}")
    print(f"  Got:      {result}")

print("\n" + "=" * 80)
if all_passed:
    print("All tests passed")
else:
    print("Some tests failed")
    sys.exit(1)
