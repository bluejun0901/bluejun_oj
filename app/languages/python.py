from app.languages.types import LanguageSpec

LANGUAGE = LanguageSpec(
    key="python",
    display_name="Python 3",
    source_filename="main.py",
    compile_command=None,
    run_command=("/usr/local/bin/python", "main.py"),
    default_source="""import sys


def main() -> None:
    nums = list(map(int, sys.stdin.read().split()))
    if len(nums) >= 2:
        print(nums[0] + nums[1])


if __name__ == "__main__":
    main()
""",
    aliases=("py", "python3"),
    run_process_limit=16,
)
