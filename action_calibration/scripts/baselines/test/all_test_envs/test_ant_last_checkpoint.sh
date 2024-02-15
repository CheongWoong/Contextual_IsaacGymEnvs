train_seed=$1
test_seed=100

for env_id in ContextualAntTestEasy1 ContextualAntTestEasy2 ContextualAntTestEasy3 \
    ContextualAntTestEasy4 ContextualAntTestEasy5 ContextualAntTestEasy6 \
    ContextualAntTestEasy7 ContextualAntTestEasy8 ContextualAntTestEasy9 \
    ContextualAntTestHard1 ContextualAntTestHard2 ContextualAntTestHard3 ContextualAntTestHard4
do
    for run_name in Ant ContextualAntTrain $env_id
    do
        run_dir="runs/Ant/seed_"$train_seed"/"$run_name
        checkpoint_path=$run_dir"/checkpoints/99942400.pth"
        python -m src.test \
            --checkpoint_path $checkpoint_path \
            --env_id $env_id \
            --seed $test_seed
    done
done

######################################################

run_name=ContextualAntTrain_with_oracle_sys_params
run_dir="runs/Ant/seed_"$train_seed"/"$run_name

for env_id in ContextualAntTestEasy1 ContextualAntTestEasy2 ContextualAntTestEasy3 \
    ContextualAntTestEasy4 ContextualAntTestEasy5 ContextualAntTestEasy6 \
    ContextualAntTestEasy7 ContextualAntTestEasy8 ContextualAntTestEasy9 \
    ContextualAntTestHard1 ContextualAntTestHard2 ContextualAntTestHard3 ContextualAntTestHard4
do
    checkpoint_path=$run_dir"/checkpoints/99942400.pth"
    python -m src.test_with_oracle_sys_params \
        --checkpoint_path $checkpoint_path \
        --env_id $env_id \
        --seed $test_seed
done