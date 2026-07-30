import shutil
import os

path = r"E:\Forex_US\Forex-EMA9-21\frontend\.next"
if os.path.exists(path):
    print("Deleting Next.js cache folder...")
    shutil.rmtree(path)
    print("Next.js cache folder deleted successfully!")
else:
    print("No Next.js cache folder found.")
