"""
Tokenize and process NER data for PhoBERT
"""
import os
import json
from datasets import load_from_disk
from transformers import AutoTokenizer
import argparse

def tokenize_and_align_labels(examples, tokenizer, label_to_id, max_length=200):
    """
    Tokenize examples và align labels.
    PhoBERT tokenizer không support word_ids(), nên phải align manual.
    """
    tokenized_inputs = {
        'input_ids': [],
        'attention_mask': [],
        'labels': []
    }
    
    for words, tags in zip(examples['words'], examples['tags']):
        # Tokenize từng word riêng để track alignment
        word_tokens_list = []
        word_labels_list = []
        
        for word, tag in zip(words, tags):
            # Tokenize word (không thêm special tokens)
            word_tokens = tokenizer.tokenize(word)
            
            # Nếu word bị split thành nhiều subwords
            if len(word_tokens) == 0:
                # Unknown word, dùng [UNK]
                word_tokens = [tokenizer.unk_token]
            
            word_tokens_list.append(word_tokens)
            
            # Align labels
            # First subword giữ nguyên label
            # Các subword tiếp theo: B-XXX → I-XXX, còn lại giữ nguyên
            aligned_labels = []
            for idx, token in enumerate(word_tokens):
                if idx == 0:
                    # First subword
                    aligned_labels.append(label_to_id[tag])
                else:
                    # Subsequent subwords
                    if tag.startswith('B-'):
                        # Convert B- to I-
                        i_tag = 'I-' + tag[2:]
                        aligned_labels.append(label_to_id[i_tag])
                    else:
                        # Keep same label (I- or O)
                        aligned_labels.append(label_to_id[tag])
            
            word_labels_list.append(aligned_labels)
        
        # Flatten tokens và labels
        all_tokens = [token for word_tokens in word_tokens_list for token in word_tokens]
        all_labels = [label for labels in word_labels_list for label in labels]
        
        # Truncate nếu quá dài (trừ đi 2 cho [CLS] và [SEP])
        max_seq_length = max_length - 2
        if len(all_tokens) > max_seq_length:
            all_tokens = all_tokens[:max_seq_length]
            all_labels = all_labels[:max_seq_length]
        
        # Add [CLS] và [SEP]
        tokens_with_special = [tokenizer.cls_token] + all_tokens + [tokenizer.sep_token]
        labels_with_special = [-100] + all_labels + [-100]  # -100 = ignore
        
        # Convert tokens to ids
        input_ids = tokenizer.convert_tokens_to_ids(tokens_with_special)
        
        # Create attention mask
        attention_mask = [1] * len(input_ids)
        
        # Padding
        padding_length = max_length - len(input_ids)
        if padding_length > 0:
            input_ids = input_ids + [tokenizer.pad_token_id] * padding_length
            attention_mask = attention_mask + [0] * padding_length
            labels_with_special = labels_with_special + [-100] * padding_length
        
        # Add to batch
        tokenized_inputs['input_ids'].append(input_ids)
        tokenized_inputs['attention_mask'].append(attention_mask)
        tokenized_inputs['labels'].append(labels_with_special)
    
    return tokenized_inputs

def process_dataset(input_dir='data/raw', output_dir='data/processed', 
                   model_name='vinai/phobert-base', max_length=200):
    """
    Process dataset: tokenize and align labels
    """
    print(f"📥 Loading dataset from {input_dir}...")
    dataset = load_from_disk(input_dir)
    
    print(f"🤖 Loading tokenizer: {model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=False)
    
    # Create label mappings
    print("🏷️  Creating label mappings...")
    all_labels = set()
    for example in dataset['train']:
        all_labels.update(example['tags'])
    
    label_names = sorted(list(all_labels))
    label_to_id = {label: idx for idx, label in enumerate(label_names)}
    id_to_label = {idx: label for label, idx in label_to_id.items()}
    
    print(f"   Total unique labels: {len(label_names)}")
    
    # Process each split
    print("\n🔄 Processing splits...")
    from datasets import Dataset, DatasetDict
    processed_dataset = {}
    
    for split_name in dataset.keys():
        print(f"\n   Processing {split_name}...")
        split_data = dataset[split_name]
        
        # Tokenize and align
        processed = split_data.map(
            lambda examples: tokenize_and_align_labels(
                examples, tokenizer, label_to_id, max_length
            ),
            batched=True,
            batch_size=100,
            remove_columns=split_data.column_names,
            desc=f"Tokenizing {split_name}"
        )
        
        processed_dataset[split_name] = processed
        print(f"   ✅ {split_name}: {len(processed)} samples")
    
    # Save processed dataset
    print(f"\n💾 Saving processed dataset to {output_dir}...")
    os.makedirs(output_dir, exist_ok=True)
    
    dataset_dict = DatasetDict(processed_dataset)
    dataset_dict.save_to_disk(output_dir)
    
    # Save label mappings
    label_config = {
        'label_names': label_names,
        'label_to_id': label_to_id,
        'id_to_label': {str(k): v for k, v in id_to_label.items()},  # JSON needs string keys
        'num_labels': len(label_names),
        'model_name': model_name,
        'max_length': max_length
    }
    
    with open(f'{output_dir}/label_config.json', 'w', encoding='utf-8') as f:
        json.dump(label_config, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Label config saved to {output_dir}/label_config.json")
    
    # Print sample
    print("\n📋 Sample processed data:")
    sample = processed_dataset['train'][0]
    print(f"   Input IDs length: {len(sample['input_ids'])}")
    print(f"   Labels length: {len(sample['labels'])}")
    print(f"   First 20 input IDs: {sample['input_ids'][:20]}")
    print(f"   First 20 labels: {sample['labels'][:20]}")
    
    # Decode sample to verify
    print("\n🔍 Decoded sample (first 15 tokens):")
    tokens = tokenizer.convert_ids_to_tokens(sample['input_ids'][:15])
    labels = sample['labels'][:15]
    for token, label_id in zip(tokens, labels):
        label = id_to_label.get(label_id, 'IGNORE' if label_id == -100 else 'UNKNOWN')
        print(f"   {token:20} → {label}")
    
    # Statistics
    print("\n📊 Dataset statistics:")
    for split_name, split_data in processed_dataset.items():
        avg_length = sum(sum(1 for x in sample['attention_mask'] if x == 1) 
                        for sample in split_data) / len(split_data)
        print(f"   {split_name}: avg sequence length = {avg_length:.1f}")
    
    return dataset_dict, label_config

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='data/raw', help='Input directory')
    parser.add_argument('--output', default='data/processed', help='Output directory')
    parser.add_argument('--model', default='vinai/phobert-base', help='Model name')
    parser.add_argument('--max_length', type=int, default=200, help='Max sequence length')
    args = parser.parse_args()
    
    print("="*80)
    print("DATA PREPROCESSING FOR NER")
    print("="*80)
    
    dataset, label_config = process_dataset(
        args.input, args.output, args.model, args.max_length
    )
    
    print("\n" + "="*80)
    print("✅ DATA PROCESSING COMPLETED!")
    print("="*80)