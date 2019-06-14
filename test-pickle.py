import malloovia
problem = malloovia.read_problems_from_github(dataset="problem1", _id="example")
phase_i_solution = malloovia.PhaseI(problem).solve()
print(phase_i_solution.solving_stats.optimal_cost)
phase_i_solution.allocation._inspect()

import pickle
with open("kk.pickle", "wb") as f:
    pickle.dump(phase_i_solution.allocation,f)

print("Escrito con éxito en pickle")
with open("kk.pickle", "rb") as f:
    a = pickle.load(f)

print("Leido con éxito del pickle. Esto es lo que he leido")
a._inspect()
