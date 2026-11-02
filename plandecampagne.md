
**What we have**
 ✓ Endgame state generator
 ✓ Solver given perfect information

**What we need**
 ✗ Bot arena
 ✗ Random bot
 ✗ Heuristic bot
 ✗ Dataset (gamestate -> label)
 ✗ Neural net

**How we do it**
1. Bot arena
   1. Deck + hand manager
   2. Determine bot interface
   3. Tournament manager
   
2. Random bot
   1. Just makes random moves

3. Heuristic bot
   1. Determine next move using hand size + value
   2. Measure performance against random bot

4. Generate dataset
   1. For each trumpsuit, sample random hands and update shared gametree
   2. Extract labels

5. Neural net
   1. Determine inputs
   2. Determine outputs
   3. Determine layout
   4. Implement ML...
   5. Measure performance against bots