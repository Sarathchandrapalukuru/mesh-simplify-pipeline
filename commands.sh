# conda
conda init

conda env list # gives list of envs in the conda currently
conda env remove -n {virtual env name}
conda create -n {virtual env name} python=3.10.13 -y # for this project {1st_env}
conda activate 2d_to_3d
conda deactivate

conda install -c conda-forge cudatoolkit=11.8 -y

python run.py examples/{__nameofthephoto__.png} --output-dir output/ --bake-texture


# flow 
python pipeline\phase1_reconstruct\reconstruct.py --input_image examples/chair.png --run_id chair_run1
python pipeline\phase2_remesh\remesh.py --run_id chair_run1
blender --background --python .\pipeline\phase3_evaluate\render_harness.py -- --run-dir "data/outputs/chair_run1"
python -m pipeline.phase3_evaluate.metrics data/outputs/chair_run1 

 $env:PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"                         
python train_simplifier.py 

# Single continuous PowerShell session required
vcvars64.bat                                    # VS2022 Build Tools, MSVC v143 pinned (14.44 too new for CUDA 11.8)
$env:PATH = "<CUDA 11.8 bin path>;" + $env:PATH  # CUDA 11.8 bin prepended
$env:CUDACXX = "<path to nvcc.exe>"              # explicit CUDA compiler path
$env:CMAKE_GENERATOR = "Ninja"
$env:NVCC_APPEND_FLAGS = "-allow-unsupported-compiler"


conda activate 3d_clean
pip install kaolin==0.18.0 -f https://nvidia-kaolin.s3.us-east-2.amazonaws.com/torch-2.7.1_cu118.html
$env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"   # reduce fragmentation-related OOM on 4GB VRAM