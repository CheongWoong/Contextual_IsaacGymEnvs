seed=0

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
        --anneal_lr \
        --track \
        --wandb_project_name Ant_training \
        --wandb_entity cw-kang \
        --capture_video
done

######################################################

env_id=ContextualAntTrain

python -m src.train_osi_true \
    --env_id $env_id \
    --seed $seed \
    --total_timesteps 100000000 \
    --anneal_lr \
    --track \
    --wandb_project_name Ant_training \
    --wandb_entity cw-kang \
    --capture_video