import os
import kaggle

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
data_folder = os.path.join(project_root, "data")
os.makedirs(data_folder, exist_ok=True)

#Importing dataset from Kaggle. Must have token in .kaggle folder. It downloads and unzip: images, obs_and_meta, and bonus folders
kaggle.api.authenticate()
kaggle.api.dataset_download_files('travisdaws/spatiotemporal-wildlife-dataset', path=data_folder, unzip=True)

#Making Marker file to check if user ran this script before running main()
with open(os.path.join(data_folder, ".download_complete"), "w") as f:
    f.write("done")