import sys
import types_pb2
from google.protobuf import text_format

def main(filename):
    """
    Tries to parse a binary payload file with prometheus.WriteRequest protobuf.
    """
    try:
        with open(filename, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        sys.exit(1)

    write_request = types_pb2.WriteRequest()

    try:
        print(f"Attempting to parse {len(data)} bytes from '{filename}'...")
        write_request.ParseFromString(data)
        print("Successfully parsed the WriteRequest!")
        
        print("\n--- Parsed Data (first 2 timeseries) ---")
        for i, ts in enumerate(write_request.timeseries[:2]):
            labels = {l.name: l.value for l in ts.labels}
            samples = [(s.value, s.timestamp) for s in ts.samples]
            print(f"Timeseries {i+1}:")
            print(f"  Labels: {labels}")
            print(f"  Samples: {samples}")
        
    except Exception as e:
        print("\n--- FAILED to parse the WriteRequest ---")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_parser.py <path_to_payload.bin>")
        sys.exit(1)
    main(sys.argv[1]) 