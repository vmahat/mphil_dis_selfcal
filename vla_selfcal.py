import os
import subprocess
import logging
import sys


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("selfcal")

# Define paths and parameters
msfile = "/beegfs/general/mahatmav/aa2/msv2/16B-251/pipeline.60631.81245370349/16B-251_3C147_Aarray_Sband_calib.ms"  # Path to your Measurement Set
output_dir = "/beegfs/general/mahatmav/aa2/msv2/16B-251/pipeline.60631.81245370349/"     # Directory to store output files

try:
    os.makedirs(output_dir, exist_ok=True)
except:
    print("Cannot make output directory!")
    sys.exit()

casa_path = "/soft/casa-latest/bin/casa"  # Path to CASA (use the correct path)

# Self-calibration parameters
solution_intervals = ["inf", "1min", "30s", "10s", "int"]  # Each consecutive round of the imaging-calibration cycle will use these time intervals to determine gain solutions for the observation

gain_solutions = []  # Store gain calibration tables

# Imaging parameters for CASA tclean
imaging_params = {
    "imsize": [2048, 2048],          # Image size (pixels)
    "cell": "0.075arcsec",           # Pixel scale (arcseconds)
    "weighting": "briggs",           # Weighting scheme
    "robust": -1.0,                  # Robust weighting factor (typically -1 to +1)
    "threshold": "1.0mJy",           # Threshold for CLEAN (in mJy)
    "mask": "3.0",                   # Masking threshold (in mJy)
    "niter": 100,                 # Number of minor cycles (iterations)
    "specmode": "mfs",               # Multi-frequency synthesis (MFS)
    "padding": 1.4,                  # Padding factor for imaging
    "interactive": False,            # Run interactively (set to False for no GUI)
}

# Function to run a command and check output
def run_command(cmd, shell=False):
    try:
        logger.info(f"Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
        subprocess.run(cmd, shell=shell, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e}")
        raise

# Function to run CASA commands
def run_casa_command(casa_script):
    casa_cmd = f"{casa_path} --nogui -c {casa_script}"
    run_command(casa_cmd, shell=True)

# Self-calibration loop
for idx, solint in enumerate(solution_intervals):
    logger.info(f"Starting self-calibration cycle {idx + 1} with solint={solint}")

    # CASA imaging step using tclean
    image_prefix = f"{output_dir}/selfcal_cycle_{idx + 1}"

    # CASA calibration script
    gain_table = f"{output_dir}/gains_cycle_{idx + 1}.cal"
    casa_script = f"""
from casatasks import tclean,ft,gaincal,applycal

from casatasks import tclean

# Perform imaging with tclean
tclean(
    vis='{msfile}',
    imagename='{image_prefix}',
    imsize={imaging_params['imsize']},
    cell='{imaging_params['cell']}',
    weighting='{imaging_params['weighting']}',
    robust={imaging_params['robust']},
    threshold='{imaging_params['threshold']}',
    niter={imaging_params['niter']},
    specmode='{imaging_params['specmode']}',
    interactive={imaging_params['interactive']}
)

# Predict
ft(vis='{msfile}', model='{image_prefix}.model', usescratch=True)

# Perform gain calibration
gaincal(vis='{msfile}', caltable='{gain_table}', solint='{solint}', refant='ea23', gaintype='G', calmode='p')

# Apply calibration solutions to the MS
applycal(vis='{msfile}', gaintable={gain_solutions + [gain_table]})
"""
    script_path = f"{output_dir}/casa_selfcal_cycle_{idx + 1}.py"
    with open(script_path, "w") as f:
        f.write(casa_script)

    # Run CASA script for calibration
    run_casa_command(script_path)
    #gain_solutions.append(gain_table) # Don't apply previous solutions (only needed when doing amp selfcal)

    # Check if improvement is sufficient
    residual_image = f"{image_prefix}-residual.fits"
    if idx > 0:
        prev_residual_image = f"{output_dir}/selfcal_cycle_{idx}-residual.fits"
        # Compare residuals here (use a tool to assess noise or improvement threshold)
        logger.info(f"Compare {residual_image} with {prev_residual_image}")
        # If no significant improvement, break the loop

    # Prepare for next cycle
    initial_model = f"{image_prefix}-model.fits"

logger.info("Self-calibration completed successfully!")

