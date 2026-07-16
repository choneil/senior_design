def write_gcode_to_file(filename, gcode_lines):
    """
    Writes G-code lines to a file.
    Each line is written on a new line.
    """

    try:
        with open(filename, "w", newline="\n", encoding="utf-8") as f:
            for line in gcode_lines:
                f.write(line + "\n")

        print(f"G-code written to: {filename}")

    except Exception as e:
        print("Error writing file:", e)
