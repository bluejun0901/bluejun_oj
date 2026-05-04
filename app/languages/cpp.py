from app.languages.types import LanguageSpec

LANGUAGE = LanguageSpec(
    key="cpp",
    display_name="C++17",
    source_filename="main.cpp",
    compile_command=(
        "/usr/bin/g++",
        "-std=c++17",
        "-O2",
        "-pipe",
        "-o",
        "main",
        "main.cpp",
    ),
    run_command=("./main",),
    default_source="""#include <iostream>

using namespace std;

int main() {
    long long a, b;
    if (!(cin >> a >> b)) {
        return 0;
    }
    cout << a + b << "\\n";
    return 0;
}
""",
    aliases=("c++", "cc", "cxx"),
    compile_process_limit=64,
)
