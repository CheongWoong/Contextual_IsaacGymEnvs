device_id=$1

for seed in 0 1 2 3 4
do
    env_id=ContextualAntTrain

    python -m src.v2.train_osi_true_student \
        --env_id $env_id \
        --seed $seed \
        --total_timesteps 100000000 \
        --device_id $device_id \
        --anneal_lr \
        --checkpoint_path "runs/training/seed_"$seed"/"$env_id"_osi_true/checkpoints/99942400.pth"
done