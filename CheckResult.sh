#!/bin/zsh
# Function to compare two files
compare_files() {
    local file1=$1
    local file2=$2
    local pair_number=$3

    echo "Comparing arbitrages found in block $pair_number: $file1 and $file2"
    echo "----------------------------------------"

    if [ ! -f "$file1" ] || [ ! -f "$file2" ]; then
        echo "Error: One or both files do not exist."
        return 1
    fi

    diff_output=$(diff "$file1" "$file2")
    diff_exit_code=$?

    if [ $diff_exit_code -eq 0 ]; then
        echo "The files are identical"
        echo "OK!"
    else
        echo "The files are different. Here's the diff:"
        echo "$diff_output"
    fi

    echo "----------------------------------------"
    echo
}

# Main script
echo "File Comparison Script"
echo "====================="

for i in {40784970..40784980}
do
    compare_files "tests/${i}_res" "tests/${i}_ref" "$i"
done

echo "All comparisons completed."