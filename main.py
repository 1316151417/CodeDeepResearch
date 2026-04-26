import os

import dotenv
dotenv.load_dotenv()

from pipeline import run_pipeline


def main():
    project_path = os.getcwd()
    if not os.path.isdir(project_path):
        print(f"错误: {project_path} 不是有效目录")
        return 1

    run_pipeline(settings_path=None)
    return 0


if __name__ == "__main__":
    exit(main())
