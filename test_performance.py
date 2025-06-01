import time
import json
from src.utils.llm_handler import apply_post_processing_rules

def measure_performance():
    """Measure the performance of the optimized post-processing rules function"""
    print("\n=== Measuring Post-Processing Performance ===")
    
    # Create a larger test dataset
    large_test_data = {}
    for i in range(1, 201):  # Create 200 fields
        if i % 3 == 0:  # Make every third field a checkbox
            large_test_data[f"test_field_{i}_check"] = "yes" if i % 2 == 0 else "no"
        else:
            large_test_data[f"test_field_{i}"] = f"Value {i}"
    
    # Add specific fields that trigger various rules
    special_fields = {
        "voltage": "220",
        "hz": "50",
        "psi": "75",
        "production_speed": "60",
        "hmi_10_check": "YES",
        "hmi_15_check": "YES",
        "hmi_5_7_check": "YES",
        "touch_screen_10inch_check": "YES",
        "touch_screen_15inch_check": "YES",
        "plc_b&r_check": "YES",
        "plc_allen_bradley_check": "YES",
        "plc_siemens_check": "YES",
        "beacon_tri_color_check": "YES",
        "beacon_red_check": "NO",
        "beacon_green_check": "NO",
        "beacon_amber_check": "NO",
        "explosion_proof_check": "YES",
        "filling_system_check": "YES",
        "electric_motor_check": "YES",
        "servo_drive_check": "YES",
        "pneumatic_actuator_check": "NO"
    }
    large_test_data.update(special_fields)
    
    print(f"Test dataset contains {len(large_test_data)} fields")
    
    # Run multiple times to get consistent measurements
    num_runs = 5
    times = []
    
    for run in range(1, num_runs + 1):
        print(f"\nRun {run}/{num_runs}:")
        start_time = time.time()
        
        # Apply post-processing rules
        corrected_data = apply_post_processing_rules(large_test_data, {})
        
        execution_time = time.time() - start_time
        times.append(execution_time)
        print(f"Processed {len(large_test_data)} fields in {execution_time:.4f} seconds")
        print(f"Average time per field: {(execution_time * 1000) / len(large_test_data):.4f} ms")
    
    # Calculate average time
    avg_time = sum(times) / len(times)
    print(f"\nAverage execution time over {num_runs} runs: {avg_time:.4f} seconds")
    print(f"Average time per field: {(avg_time * 1000) / len(large_test_data):.4f} ms")
    
    # Verify a few key corrections were made
    print("\nVerifying key corrections from final run:")
    print(f"Voltage: '{corrected_data['voltage']}'")
    print(f"HMI choices: HMI 15\"={corrected_data['hmi_15_check']}, HMI 10\"={corrected_data['hmi_10_check']}, HMI 5.7\"={corrected_data['hmi_5_7_check']}")
    print(f"Touch screen: 15\"={corrected_data['touch_screen_15inch_check']}, 10\"={corrected_data['touch_screen_10inch_check']}")
    print(f"PLC choice: B&R={corrected_data['plc_b&r_check']}, Allen Bradley={corrected_data['plc_allen_bradley_check']}, Siemens={corrected_data['plc_siemens_check']}")
    print(f"Beacon lights: Red={corrected_data['beacon_red_check']}, Green={corrected_data['beacon_green_check']}, Amber={corrected_data['beacon_amber_check']}")
    print(f"Explosion proof environment handling: Electric motor={corrected_data['electric_motor_check']}, Pneumatic={corrected_data['pneumatic_actuator_check']}")

if __name__ == "__main__":
    measure_performance() 