"""
Download PhoNER_COVID19 dataset from Hugging Face
"""
from datasets import load_dataset
import os
import argparse

def download_and_save_data(output_dir='data/raw'):
    """Download dataset and save to local"""
    print("Downloading PhoNER_COVID19 from Hugging Face...")
    
    # Load dataset
    from datasets import load_dataset

    ds = load_dataset("hungphongtrn/PhoNer_Covid19")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Save to disk
    ds.save_to_disk(output_dir)
    print(f"Dataset saved to {output_dir}")
    
    # Print statistics
    print(f"Dataset Statistics:")
    print(f"Train samples: {len(ds['train'])}")
    print(f"Validation samples: {len(ds['validation'])}")
    print(f"Test samples: {len(ds['test'])}")
    
    
    return ds

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='data/raw', help='Output directory')
    args = parser.parse_args()
    
    dataset = download_and_save_data(args.output)