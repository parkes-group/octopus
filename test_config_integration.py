"""Integration test: Verify all configuration changes work together"""
from app.api_client import OctopusAPIClient
from app.cache_manager import CacheManager
from app.config import Config

print("Integration Test: All Configuration Changes")
print("=" * 60)

# Test 1: API Configuration
print("\n1. API Configuration:")
config = OctopusAPIClient._get_config()
print(f"   [OK] Base URL: {config['base_url']}")
print(f"   [OK] Product Code: {config['product_code']}")
print(f"   [OK] Timeout: {config['timeout']} seconds")
assert config['base_url'] == Config.OCTOPUS_API_BASE_URL
assert config['product_code'] == Config.OCTOPUS_PRODUCT_CODE
assert config['timeout'] == Config.OCTOPUS_API_TIMEOUT

# Test 2: Region Names
print("\n2. Region Names:")
print(f"   [OK] Region names count: {len(config['region_names'])}")
assert config['region_names'] == Config.OCTOPUS_REGION_NAMES
assert config['region_names']['A'] == 'Eastern England'

# Test 3: URL Construction
print("\n3. URL Construction:")
regions_url = config['get_regions_url']()
prices_url = config['get_prices_url']('A')
print(f"   [OK] Regions URL: {regions_url[:50]}...")
print(f"   [OK] Prices URL: {prices_url[:60]}...")
assert regions_url == Config.get_regions_url()
assert prices_url == Config.get_prices_url('A')

# Test 4: Cache Configuration
print("\n4. Cache Configuration:")
cache_expiry = CacheManager._get_cache_expiry_minutes()
print(f"   [OK] Cache expiry: {cache_expiry} minutes")
assert cache_expiry == Config.CACHE_EXPIRY_MINUTES

print("\n" + "=" * 60)
print("[PASS] All configuration changes verified successfully!")
print("=" * 60)

