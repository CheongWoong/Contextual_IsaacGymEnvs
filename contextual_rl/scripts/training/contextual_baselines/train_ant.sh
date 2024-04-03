device_id=$1

for seed in 0 1 2 3 4
do
    env_id=ContextualAntTrain

    python -m src.train_ppo_stacked \
        --env_id $env_id \
        --seed $seed \
        --total_timesteps 100000000 \
        --device_id $device_id \
        --anneal_lr

    python -m src.train_osi_true \
        --env_id $env_id \
        --seed $seed \
        --total_timesteps 100000000 \
        --device_id $device_id \
        --anneal_lr
done