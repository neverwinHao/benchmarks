  source ~/.local/bin/env && uv run swtbench-infer .llm_config/claude-opus.json \                                                                                        
    --select instances_10.txt \                                                                                                                                          
    --n-critic-runs 1 \                                                                                                                                                  
    --max-iterations 100 \                                                                                                                                               
    --workspace docker \                                                                                                                                               
    --num-workers 2 \                     
    --n-limit 10 \                        
    --disable-condenser 