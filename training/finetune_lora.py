"""Entrena (fine-tuning con LoRA) un modelo abierto con tu dataset.

Necesita una GPU NVIDIA. Si no tienes, usa Google Colab (gratis): ver README.

Uso:
    pip install -r requirements-train.txt
    python training/finetune_lora.py                       # modelo 1.5B (rápido)
    python training/finetune_lora.py --base-model Qwen/Qwen2.5-Coder-7B-Instruct --qlora

Resultado:
    training/output/adapter/   -> solo los pesos LoRA (pequeño)
    training/output/merged/    -> modelo completo listo para convertir a GGUF (Ollama)
"""
import argparse
import gc
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--base-model", default="Qwen/Qwen2.5-Coder-1.5B-Instruct")
    p.add_argument("--data", default=str(ROOT / "training" / "dataset.jsonl"))
    p.add_argument("--output", default=str(ROOT / "training" / "output"))
    p.add_argument("--epochs", type=float, default=3)
    p.add_argument("--lr", type=float, default=2e-4)
    p.add_argument("--batch-size", type=int, default=2)
    p.add_argument("--max-length", type=int, default=2048)
    p.add_argument("--lora-r", type=int, default=16)
    p.add_argument("--qlora", action="store_true", help="cargar en 4 bits (para modelos 7B en GPU de 16 GB)")
    return p.parse_args()


def _supported(cls, **kwargs) -> dict:
    """Solo pasa los argumentos que acepta la versión instalada de la librería."""
    params = inspect.signature(cls.__init__).parameters
    return {k: v for k, v in kwargs.items() if k in params}


def main() -> None:
    args = parse_args()

    import torch
    from datasets import load_dataset
    from peft import LoraConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import SFTConfig, SFTTrainer

    if not torch.cuda.is_available():
        raise SystemExit("No hay GPU NVIDIA disponible. Usa Google Colab (ver README).")

    out = Path(args.output)
    adapter_dir, merged_dir = out / "adapter", out / "merged"
    bf16 = torch.cuda.is_bf16_supported()
    dtype = torch.bfloat16 if bf16 else torch.float16

    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    quant = None
    if args.qlora:
        quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                   bnb_4bit_compute_dtype=dtype, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(args.base_model, torch_dtype=dtype,
                                                 quantization_config=quant, device_map="auto")
    if args.qlora:
        model = prepare_model_for_kbit_training(model)
    else:
        model.enable_input_require_grads()  # necesario con gradient checkpointing
    model = get_peft_model(model, LoraConfig(
        r=args.lora_r, lora_alpha=args.lora_r * 2, lora_dropout=0.05,
        target_modules="all-linear", task_type="CAUSAL_LM"))
    for param in model.parameters():  # pesos LoRA en float32 para entrenar estable
        if param.requires_grad:
            param.data = param.data.float()
    model.print_trainable_parameters()

    dataset = load_dataset("json", data_files=args.data, split="train")
    print(f"Ejemplos de entrenamiento: {len(dataset)}")

    config = SFTConfig(**_supported(
        SFTConfig,
        output_dir=str(out / "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=4,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        logging_steps=5,
        save_strategy="no",
        bf16=bf16,
        fp16=not bf16,
        gradient_checkpointing=True,
        report_to="none",
        max_length=args.max_length,      # trl reciente
        max_seq_length=args.max_length,  # trl antiguo
    ))
    trainer_kwargs = {"model": model, "args": config, "train_dataset": dataset}
    trainer_params = inspect.signature(SFTTrainer.__init__).parameters
    trainer_kwargs["processing_class" if "processing_class" in trainer_params else "tokenizer"] = tokenizer
    trainer = SFTTrainer(**trainer_kwargs)
    trainer.train()
    trainer.save_model(str(adapter_dir))
    print(f"Adaptador LoRA guardado en {adapter_dir}")

    # Fusionar LoRA con el modelo base para poder usarlo en Ollama
    del trainer, model
    gc.collect()
    torch.cuda.empty_cache()
    base = AutoModelForCausalLM.from_pretrained(args.base_model, torch_dtype=torch.float16,
                                                device_map="auto")
    merged = PeftModel.from_pretrained(base, str(adapter_dir)).merge_and_unload()
    merged.save_pretrained(str(merged_dir), safe_serialization=True)
    tokenizer.save_pretrained(str(merged_dir))
    print(f"Modelo fusionado guardado en {merged_dir}")
    print("Siguiente paso: convertir a GGUF (ver README, sección 'Entrenar').")


if __name__ == "__main__":
    main()
