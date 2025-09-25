#!/usr/bin/env python3
"""
Test script to validate the few-shot learning monitoring functionality.
This script tests the database functions and UI components for monitoring performance.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.utils.crm_utils import (
    init_db, 
    get_few_shot_statistics, 
    get_field_examples, 
    get_all_field_names,
    create_sample_few_shot_data,
    get_similar_examples
)

def test_database_initialization():
    """Test that the database can be initialized with few-shot learning tables."""
    print("🧪 Testing database initialization...")
    
    try:
        init_db()
        print("✅ Database initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

def test_sample_data_creation():
    """Test that sample data can be created for testing."""
    print("🧪 Testing sample data creation...")
    
    try:
        # Create sample data
        success = create_sample_few_shot_data()
        if success:
            print("✅ Sample data created successfully")
            return True
        else:
            print("❌ Sample data creation failed")
            return False
    except Exception as e:
        print(f"❌ Sample data creation failed with exception: {e}")
        return False

def test_statistics_retrieval():
    """Test that statistics can be retrieved from the database."""
    print("🧪 Testing statistics retrieval...")
    
    try:
        stats = get_few_shot_statistics()
        
        if not stats:
            print("❌ No statistics returned")
            return False
        
        # Check required fields
        required_fields = ['total_examples', 'by_machine_type', 'by_template_type', 'top_fields', 'overall']
        for field in required_fields:
            if field not in stats:
                print(f"❌ Missing required field: {field}")
                return False
        
        print(f"✅ Statistics retrieved successfully:")
        print(f"   - Total examples: {stats.get('total_examples', 0)}")
        print(f"   - Overall success rate: {stats.get('overall', {}).get('overall_success_rate', 0):.1%}")
        print(f"   - Average confidence: {stats.get('overall', {}).get('avg_confidence', 0):.2f}")
        
        return True
    except Exception as e:
        print(f"❌ Statistics retrieval failed: {e}")
        return False

def test_field_examples_retrieval():
    """Test that field examples can be retrieved with filtering."""
    print("🧪 Testing field examples retrieval...")
    
    try:
        # Test getting all examples
        all_examples = get_field_examples(limit=10)
        print(f"✅ Retrieved {len(all_examples)} examples (all types)")
        
        # Test filtering by machine type
        filling_examples = get_field_examples(machine_type='filling', limit=5)
        print(f"✅ Retrieved {len(filling_examples)} filling machine examples")
        
        # Test filtering by field name
        speed_examples = get_field_examples(field_name='production_speed', limit=5)
        print(f"✅ Retrieved {len(speed_examples)} production_speed examples")
        
        return True
    except Exception as e:
        print(f"❌ Field examples retrieval failed: {e}")
        return False

def test_field_names_retrieval():
    """Test that field names can be retrieved."""
    print("🧪 Testing field names retrieval...")
    
    try:
        field_names = get_all_field_names()
        print(f"✅ Retrieved {len(field_names)} unique field names:")
        for name in field_names:
            print(f"   - {name}")
        
        return True
    except Exception as e:
        print(f"❌ Field names retrieval failed: {e}")
        return False

def test_similar_examples():
    """Test that similar examples can be found."""
    print("🧪 Testing similar examples search...")
    
    try:
        # Test search for production speed
        similar = get_similar_examples("production speed 60 bottles per minute", "filling", "default", limit=3)
        print(f"✅ Found {len(similar)} similar examples for production speed search")
        
        # Test search for SortStar
        similar = get_similar_examples("SortStar bottle unscrambler", "sortstar", "sortstar", limit=3)
        print(f"✅ Found {len(similar)} similar examples for SortStar search")
        
        return True
    except Exception as e:
        print(f"❌ Similar examples search failed: {e}")
        return False

def test_ui_components():
    """Test that UI components can be imported and basic functions work."""
    print("🧪 Testing UI components...")
    
    try:
        # Test importing UI components
        from src.ui.ui_pages import show_few_shot_management_page
        print("✅ UI components imported successfully")
        
        # Test that the function exists and is callable
        if callable(show_few_shot_management_page):
            print("✅ show_few_shot_management_page function is callable")
            return True
        else:
            print("❌ show_few_shot_management_page is not callable")
            return False
    except Exception as e:
        print(f"❌ UI components test failed: {e}")
        return False

def run_all_tests():
    """Run all tests and provide a summary."""
    print("🚀 Starting Few-Shot Learning Monitoring Validation Tests\n")
    
    tests = [
        ("Database Initialization", test_database_initialization),
        ("Sample Data Creation", test_sample_data_creation),
        ("Statistics Retrieval", test_statistics_retrieval),
        ("Field Examples Retrieval", test_field_examples_retrieval),
        ("Field Names Retrieval", test_field_names_retrieval),
        ("Similar Examples Search", test_similar_examples),
        ("UI Components", test_ui_components)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        result = test_func()
        results.append((test_name, result))
    
    # Summary
    print(f"\n{'='*50}")
    print("📊 TEST SUMMARY")
    print(f"{'='*50}")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 All tests passed! The few-shot learning monitoring system is working correctly.")
        print("\n📋 Next steps:")
        print("1. Run the Streamlit app: streamlit run app.py")
        print("2. Navigate to the 'Few-Shot Learning' page")
        print("3. Click 'Create Sample Data' to populate the database")
        print("4. Explore the performance metrics and example management features")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please check the errors above.")
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
