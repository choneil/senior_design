from centroid import load_centroid_file
from gcode_generator import build_gcode
from file_writer import write_gcode_to_file

def main():
    input_file = "test_centroid.csv"
    output_file = "test_output.gcode"

    print("Reading CSV...")
    components = load_centroid_file(input_file)

    print(f"Loaded {len(components)} components")

    print("Generating G-code...")
    gcode = build_gcode(components)

    print("Writing G-code to file...")
    write_gcode_to_file(output_file, gcode)

    print("\n--- GCODE OUTPUT ---")
    for line in gcode:
        print(line)

    print("\nDone.")

if __name__ == "__main__":
    main()
