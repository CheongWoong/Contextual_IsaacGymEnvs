device_id=$1

for seed in 0 1 2 3 4
do
    for env_id in Ant \
        ContextualAntTrain \
        ContextualAntTestEasy1 ContextualAntTestEasy2 ContextualAntTestEasy3 \
        ContextualAntTestEasy4 ContextualAntTestEasy5 ContextualAntTestEasy6 \
        ContextualAntTestEasy7 ContextualAntTestEasy8 ContextualAntTestEasy9 \
        ContextualAntTestHard1 ContextualAntTestHard2 ContextualAntTestHard3 ContextualAntTestHard4
    do
        python -m src.train_ppo \
            --env_id $env_id \
            --seed $seed \
            --total_timesteps 100000000 \
            --device_id $device_id \
            --anneal_lr
    done

    env_id=Ant
    
    python -m src.train_ppo_stacked \
        --env_id $env_id \
        --seed $seed \
        --total_timesteps 100000000 \
        --device_id $device_id \
        --anneal_lr
done