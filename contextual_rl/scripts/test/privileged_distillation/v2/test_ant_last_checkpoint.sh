device_id=$1

test_seed=100

train_env_id=ContextualAntTrain

for train_seed in 0 1 2 3 4
do
    for env_id in ContextualAntTestEasy1 ContextualAntTestEasy2 ContextualAntTestEasy3 \
        ContextualAntTestEasy4 ContextualAntTestEasy5 ContextualAntTestEasy6 \
        ContextualAntTestEasy7 ContextualAntTestEasy8 ContextualAntTestEasy9 \
        ContextualAntTestHard1 ContextualAntTestHard2 ContextualAntTestHard3 ContextualAntTestHard4
    do
        run_name=$train_env_id"_osi_true_student"
        run_dir="runs/training/seed_"$train_seed"/"$run_name

        checkpoint_path=$run_dir"/checkpoints/99942400.pth"
        
        python -m src.test_osi_true_student \
            --checkpoint_path $checkpoint_path \
            --env_id $env_id \
            --device_id $device_id \
            --seed $test_seed
    done
done