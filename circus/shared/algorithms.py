import matplotlib
matplotlib.use('Agg')
import os
os.environ['MDP_DISABLE_SKLEARN']='yes'
import scipy.optimize, numpy, pylab, mdp, scipy.spatial.distance, scipy.stats, progressbar
from circus.shared.files import load_data

def distancematrix(data, weight=None):
    
    if weight is None:
        weight = numpy.ones(data.shape[1])/data.shape[1]    
    distances = scipy.spatial.distance.pdist(data, 'wminkowski', p=2, w=numpy.sqrt(weight))**2
    return distances

def fit_rho_delta(xdata, ydata, display=False, threshold=numpy.exp(-3**2), max_clusters=10, save=False):

    gamma = xdata * ydata

    def powerlaw(x, a, b, k): 
        with numpy.errstate(all='ignore'):
            return a*(x**k) + b

    try:
        sort_idx     = numpy.argsort(xdata)    
        result, pcov = scipy.optimize.curve_fit(powerlaw, xdata, numpy.log(ydata), [1, 1, 0])
        data_fit     = numpy.exp(powerlaw(xdata[sort_idx], result[0], result[1], result[2]))
        xaxis        = numpy.linspace(xdata.min(), xdata.max(), 1000)
        padding      = threshold
    except Exception:
        return numpy.argsort(gamma)

    if display:
        fig      = pylab.figure(figsize=(15, 5))
        ax       = fig.add_subplot(111)
        
        ax.plot(xdata, ydata, 'k.')
        ax.plot(xdata[sort_idx], data_fit)
        ax.set_yscale('log')
        ax.set_ylabel(r'$\delta$')
        ax.set_xlabel(r'$\rho$')

    idx      = numpy.where((xdata > padding) & (ydata > data_fit))[0]
    if len(idx) == 0:
        subidx = numpy.argsort(gamma)
    with numpy.errstate(all='ignore'):
        mask     = (xdata > padding).astype(int)
        value    = ydata - numpy.exp(powerlaw(xdata, result[0], result[1], result[2]))
        value   *= mask
        subidx   = numpy.argsort(value)[::-1]

        if display:
            ax.plot(xdata[subidx[:max_clusters]], ydata[subidx[:max_clusters]], 'ro')
            if save:
                pylab.savefig(os.path.join(save[0], 'rho_delta_%s.png' %(save[1])))
                pylab.close()
            else:
                pylab.show()
        return subidx


def rho_estimation(data, dc=None, weight=None, update=None, compute_rho=True):

    N   = len(data)
    rho = numpy.zeros(N, dtype=numpy.float32)
        
    if update is None:
        dist = distancematrix(data, weight=weight)
        didx = lambda i,j: i*N + j - i*(i+1)/2 - i - 1

        if dc is None:
            sda      = numpy.argsort(dist)
            position = numpy.round(N*2/100.)
            dc       = dist[sda][int(position)]

        if compute_rho:
            exp_dist = numpy.exp(-(dist/dc)**2)
            for i in xrange(N):   
               rho[i] = numpy.sum(exp_dist[didx(i, numpy.arange(i+1, N))]) + numpy.sum(exp_dist[didx(numpy.arange(0, i-1), i)])  
    else:
        if weight is None:
            weight   = numpy.ones(data.shape[1])/data.shape[1]

        for i in xrange(N):
            dist     = numpy.sum(weight*(data[i] - update)**2, 1)
            exp_dist = numpy.exp(-(dist/dc)**2)
            rho[i]   = numpy.sum(exp_dist)
    return rho, dist, dc


def clustering(rho, dist, dc, smart_search=0, display=None, n_min=None, max_clusters=10, save=False):

    N                 = len(rho)
    maxd              = numpy.max(dist)
    didx              = lambda i,j: i*N + j - i*(i+1)/2 - i - 1
    ordrho            = numpy.argsort(rho)[::-1]
    rho_sorted        = rho[ordrho]
    delta, nneigh     = numpy.zeros(N, dtype=numpy.float32), numpy.zeros(N, dtype=numpy.int32)
    delta[ordrho[0]]  = -1
    for ii in xrange(N):
        delta[ordrho[ii]] = maxd
        for jj in xrange(ii):
            if ordrho[jj] > ordrho[ii]:
                xdist = dist[didx(ordrho[ii], ordrho[jj])]
            else:
                xdist = dist[didx(ordrho[jj], ordrho[ii])]

            if xdist < delta[ordrho[ii]]:
                delta[ordrho[ii]]  = xdist
                nneigh[ordrho[ii]] = ordrho[jj]
    
    delta[ordrho[0]] = delta.ravel().max()  
    threshold        = n_min * numpy.exp(-max(smart_search, 4)**2)
    clust_idx        = fit_rho_delta(rho, delta, max_clusters=max_clusters, threshold=threshold)
    
    def assign_halo(idx):
        cl      = numpy.empty(N, dtype=numpy.int32)
        cl[:]   = -1
        NCLUST  = len(idx)
        cl[idx] = numpy.arange(NCLUST)
        
        # assignation
        for i in xrange(N):
            if cl[ordrho[i]] == -1:
                cl[ordrho[i]] = cl[nneigh[ordrho[i]]]
        
        # halo
        halo = cl.copy()
        if NCLUST > 1:
            bord_rho = numpy.zeros(NCLUST, dtype=numpy.float32)
            for i in xrange(N):
                idx      = numpy.where((cl[i] < cl[i+1:N]) & (dist[didx(i, numpy.arange(i+1, N))] <= dc))[0]
                if len(idx) > 0:
                    myslice  = cl[i+1:N][idx]
                    rho_aver = (rho[i] + rho[idx]) / 2.
                    sub_idx  = numpy.where(rho_aver > bord_rho[cl[i]])[0]
                    if len(sub_idx) > 0:
                        bord_rho[cl[i]] = rho_aver[sub_idx].max()
                    sub_idx  = numpy.where(rho_aver > bord_rho[myslice])[0]
                    if len(sub_idx) > 0:
                        bord_rho[myslice[sub_idx]] = rho_aver[sub_idx]
            
            idx       = numpy.where(rho < bord_rho[cl])[0]
            halo[idx] = -1

        if n_min is not None:
            for cluster in xrange(NCLUST):
                idx = numpy.where(halo == cluster)[0]
                if len(idx) < n_min:
                    halo[idx] = -1
                    NCLUST   -= 1
        return halo, NCLUST

    #print "Try to maximize the number of clusters..."
    NCLUST = 0
    for n in xrange(max_clusters):
        halo_temp, NCLUST_temp = assign_halo(clust_idx[:n+1])
        if NCLUST_temp >= NCLUST:
            halo   = numpy.array(halo_temp).copy()
            NCLUST = NCLUST_temp

    return halo, rho, delta, clust_idx


def merging(groups, sim_same_elec, data):

    def perform_merging(groups, sim_same_elec, data):
        mask      = numpy.where(groups > -1)[0]
        clusters  = numpy.unique(groups[mask])
        dmin      = numpy.inf
        to_merge  = [None, None]
        
        for ic1 in xrange(len(clusters)):
            idx1 = numpy.where(groups == clusters[ic1])[0]
            m1   = numpy.median(data[idx1], 0)
            for ic2 in xrange(ic1+1, len(clusters)):
                idx2 = numpy.where(groups == clusters[ic2])[0]
                m2   = numpy.median(data[idx2], 0)
                v_n  = m1 - m2      
                pr_1 = numpy.dot(data[idx1], v_n)
                pr_2 = numpy.dot(data[idx2], v_n)

                norm = numpy.median(numpy.abs(pr_1 - numpy.median(pr_1)))**2 + numpy.median(numpy.abs(pr_2 - numpy.median(pr_2)))**2

                with numpy.errstate(all='ignore'):  
                    dist = numpy.abs(numpy.median(pr_1) - numpy.median(pr_2))/numpy.sqrt(norm)
                    
                if dist < dmin:
                    dmin     = dist
                    to_merge = [ic1, ic2]

        if dmin < sim_same_elec:
            groups[numpy.where(groups == clusters[to_merge[1]])[0]] = clusters[to_merge[0]]
            return True, groups
        
        return False, groups

    has_been_merged = True
    mask            = numpy.where(groups > -1)[0]
    clusters        = numpy.unique(groups[mask])
    merged          = [len(clusters), 0]

    while has_been_merged:
        has_been_merged, groups = perform_merging(groups, sim_same_elec, data)
        if has_been_merged:
            merged[1] += 1
    return groups, merged

def merging_cc(comm, params, cc_merge, parallel_hdf5=False):

    def perform_merging(templates, amplitudes, result, cc_merge, distances):
        dmax      = distances.max()
        nb_temp   = templates.shape[2]/2
        idx       = numpy.where(distances == dmax)
        to_merge  = [idx[0][0], idx[1][0]]

        if dmax >= cc_merge:

            elec_ic1  = result['electrodes'][to_merge[0]]
            elec_ic2  = result['electrodes'][to_merge[1]]
            nic1      = to_merge[0] - numpy.where(result['electrodes'] == elec_ic1)[0][0]
            nic2      = to_merge[1] - numpy.where(result['electrodes'] == elec_ic2)[0][0]

            mask1     = result['clusters_' + str(elec_ic1)] > -1
            mask2     = result['clusters_' + str(elec_ic2)] > -1
            tmp1      = numpy.unique(result['clusters_' + str(elec_ic1)][mask1])
            tmp2      = numpy.unique(result['clusters_' + str(elec_ic2)][mask2])

            elements1 = numpy.where(result['clusters_' + str(elec_ic1)] == tmp1[nic1])[0]
            elements2 = numpy.where(result['clusters_' + str(elec_ic2)] == tmp2[nic2])[0]

            if len(elements1) > len(elements2):
                to_remove = to_merge[1]
                to_keep   = to_merge[0]
                elec      = elec_ic2
                elements  = elements2
            else:
                to_remove = to_merge[0]
                to_keep   = to_merge[1]
                elec      = elec_ic1
                elements  = elements1

            result['data_' + str(elec)]     = numpy.delete(result['data_' + str(elec)], elements, axis=0)
            result['clusters_' + str(elec)] = numpy.delete(result['clusters_' + str(elec)], elements) 
            result['debug_' + str(elec)]    = numpy.delete(result['debug_' + str(elec)], elements, axis=1)   
            result['times_' + str(elec)]    = numpy.delete(result['times_' + str(elec)], elements)
            result['electrodes']            = numpy.delete(result['electrodes'], to_remove)
            templates                       = numpy.delete(templates, [to_remove, to_remove + nb_temp], axis=2)
            amplitudes[to_keep][0]          = min(amplitudes[to_keep][0], amplitudes[to_remove][0])
            amplitudes[to_keep][1]          = max(amplitudes[to_keep][1], amplitudes[to_remove][1])            
            amplitudes                      = numpy.delete(amplitudes, to_remove, axis=0)
            distances                       = numpy.delete(distances, to_remove, axis=0)
            distances                       = numpy.delete(distances, to_remove, axis=1)
            return True, templates, amplitudes, result, distances
        
        return False, templates, amplitudes, result, distances

    has_been_merged = True
    templates       = load_data(params, 'templates')
    amplitudes      = load_data(params, 'limits')
    result          = load_data(params, 'clusters')
    tmp_path        = os.path.join(os.path.abspath(params.get('data', 'data_file_noext')), 'tmp')
    filename        = os.path.join(tmp_path, 'merging_cc.hdf5')
    N_e, N_t, N_tm  = templates.shape
    nb_temp         = templates.shape[2]/2
    merged          = [nb_temp, 0]

    try:
        HAVE_CUDA = True
        if parallel_hdf5:
            if nb_gpu > nb_cpu:
                gpu_id = int(comm.rank/nb_cpu)
            else:
                gpu_id = 0
        else:
            gpu_id = 0
        cmt.cuda_set_device(gpu_id)
        cmt.init()
        cmt.cuda_sync_threads()
    except Exception:
        HAVE_CUDA = False

    norm_templates = numpy.sqrt(numpy.mean(numpy.mean(templates**2,0),0))
    norm_templates = templates/norm_templates

    if comm.rank == 0:
        pbar = progressbar.ProgressBar(widgets=[progressbar.Percentage(), progressbar.Bar(), progressbar.ETA()], maxval=N_t).start()

    import h5py

    if parallel_hdf5:
        file = h5py.File(filename, 'w', driver='mpio', comm=comm)
        file.create_dataset('overlap', shape=(N_tm, N_tm, 2*N_t - 1), dtype=numpy.float32, chunks=True)
    elif comm.rank == 0:
        file = h5py.File(filename, 'w')
        file.create_dataset('overlap', shape=(N_tm, N_tm, 2*N_t - 1), dtype=numpy.float32, chunks=True)

    all_delays   = numpy.arange(1, N_t+1)
        
    if parallel_hdf5:
        local_delays = all_delays[numpy.arange(comm.rank, len(all_delays), comm.size)] 
    else:
        local_delays = all_delays      

    if parallel_hdf5 or (comm.rank == 0):

        for idelay in local_delays:
            tmp_1 = norm_templates[:, :idelay, :]
            tmp_2 = norm_templates[:, -idelay:, :]
            size  = templates.shape[0]*idelay
            if HAVE_CUDA:
                tmp_1 = cmt.CUDAMatrix(tmp_1.reshape(size, 2*nb_temp))
                tmp_2 = cmt.CUDAMatrix(tmp_2.reshape(size, 2*nb_temp))
                data  = cmt.dot(tmp_1.T, tmp_2).asarray()
            else:
                tmp_1 = tmp_1.reshape(size, 2*nb_temp)
                tmp_2 = tmp_2.reshape(size, 2*nb_temp)
                data  = numpy.dot(tmp_1.T, tmp_2)

            file.get('overlap')[:, :, idelay-1]           = data
            file.get('overlap')[:, :, 2*N_t - idelay - 1] = numpy.transpose(data)
            if comm.rank == 0:
                pbar.update(idelay)
        if comm.rank == 0:
            pbar.finish()
        file.close()

    comm.Barrier()

    if comm.rank == 0:
        distances = numpy.zeros((nb_temp, nb_temp), dtype=numpy.float32)
        file = h5py.File(filename)
        for i in xrange(nb_temp):
            distances[i, i+1:] = numpy.max(file.get('overlap')[i, i+1:nb_temp], 1)
            distances[i+1:, i] = distances[i, i+1:]
        file.close()
        os.remove(filename)
        distances /= (templates.shape[0]*N_t)

        while has_been_merged:
            has_been_merged, templates, amplitudes, result, distances = perform_merging(templates, amplitudes, result, cc_merge, distances)
            if has_been_merged:
                merged[1] += 1
    return templates, amplitudes, result, merged


def delete_mixtures(comm, params, parallel_hdf5=False):

    def remove_template(templates, amplitudes, result, mixtures):

        a, b, c = templates.shape
        removed = numpy.zeros((a, b, 0), dtype=numpy.float32)
        for count in xrange(len(mixtures)):
            to_remove = mixtures[count]
            removed   = numpy.concatenate((removed, templates[:, :, to_remove].reshape(a, b, 1)), axis=2)
            nb_temp   = templates.shape[2]/2
            elec      = result['electrodes'][to_remove]
            nic       = to_remove - numpy.where(result['electrodes'] == elec)[0][0]
            mask      = result['clusters_' + str(elec)] > -1
            tmp       = numpy.unique(result['clusters_' + str(elec)][mask])
            elements  = numpy.where(result['clusters_' + str(elec)] == tmp[nic])[0]
            
            result['data_' + str(elec)]     = numpy.delete(result['data_' + str(elec)], elements, axis=0)
            result['clusters_' + str(elec)] = numpy.delete(result['clusters_' + str(elec)], elements) 
            result['debug_' + str(elec)]    = numpy.delete(result['debug_' + str(elec)], elements, axis=1)   
            result['times_' + str(elec)]    = numpy.delete(result['times_' + str(elec)], elements)
            result['electrodes']            = numpy.delete(result['electrodes'], to_remove)
            templates                       = numpy.delete(templates, [to_remove, to_remove + nb_temp], axis=2)
            amplitudes                      = numpy.delete(amplitudes, to_remove, axis=0)
            mixtures[mixtures > to_remove] -= 1
        return templates, amplitudes, result, removed
        
    templates       = load_data(params, 'templates')
    amplitudes      = load_data(params, 'limits')
    result          = load_data(params, 'clusters')
    tmp_path        = os.path.join(os.path.abspath(params.get('data', 'data_file_noext')), 'tmp')
    filename        = os.path.join(tmp_path, 'mixtures.hdf5')
    N_e, N_t, N_tm  = templates.shape
    nb_temp         = templates.shape[2]/2
    merged          = [nb_temp, 0]
    mixtures        = []
    removed         = []

    try:
        HAVE_CUDA = True
        if parallel_hdf5:
            if nb_gpu > nb_cpu:
                gpu_id = int(comm.rank/nb_cpu)
            else:
                gpu_id = 0
        else:
            gpu_id = 0
        cmt.cuda_set_device(gpu_id)
        cmt.init()
        cmt.cuda_sync_threads()
    except Exception:
        HAVE_CUDA = False

    if comm.rank == 0:
        pbar = progressbar.ProgressBar(widgets=[progressbar.Percentage(), progressbar.Bar(), progressbar.ETA()], maxval=N_t).start()

    import h5py

    if parallel_hdf5:
        file = h5py.File(filename, 'w', driver='mpio', comm=comm)
        file.create_dataset('overlap', shape=(N_tm, N_tm, 2*N_t - 1), dtype=numpy.float32, chunks=True)
    elif comm.rank == 0:
        file = h5py.File(filename, 'w')
        file.create_dataset('overlap', shape=(N_tm, N_tm, 2*N_t - 1), dtype=numpy.float32, chunks=True)

    all_delays   = numpy.arange(1, N_t+1)
        
    if parallel_hdf5:
        local_delays = all_delays[numpy.arange(comm.rank, len(all_delays), comm.size)] 
    else:
        local_delays = all_delays      

    if parallel_hdf5 or (comm.rank == 0):

        for idelay in local_delays:
            tmp_1 = templates[:, :idelay, :]
            tmp_2 = templates[:, -idelay:, :]
            size  = templates.shape[0]*idelay
            if HAVE_CUDA:
                tmp_1 = cmt.CUDAMatrix(tmp_1.reshape(size, 2*nb_temp))
                tmp_2 = cmt.CUDAMatrix(tmp_2.reshape(size, 2*nb_temp))
                data  = cmt.dot(tmp_1.T, tmp_2).asarray()
            else:
                tmp_1 = tmp_1.reshape(size, 2*nb_temp)
                tmp_2 = tmp_2.reshape(size, 2*nb_temp)
                data  = numpy.dot(tmp_1.T, tmp_2)

            file.get('overlap')[:, :, idelay-1]           = data
            file.get('overlap')[:, :, 2*N_t - idelay - 1] = numpy.transpose(data)
            if comm.rank == 0:
                pbar.update(idelay)
        if comm.rank == 0:
            pbar.finish()
        file.close()

    comm.Barrier()

    if comm.rank == 0:
        distances = numpy.zeros((nb_temp, nb_temp), dtype=numpy.float32)
        file = h5py.File(filename)

        for i in xrange(nb_temp):
            distances[i, i+1:] = numpy.argmax(file.get('overlap')[i, i+1:nb_temp], 1)
            distances[i+1:, i] = distances[i, i+1:]

        import scipy.linalg
        overlap_0 = file.get('overlap')[:, :, N_t]
        pbar      = progressbar.ProgressBar(widgets=[progressbar.Percentage(), progressbar.Bar(), progressbar.ETA()], maxval=nb_temp).start()

        for k in xrange(nb_temp):
            idx_1      = numpy.where(result['electrodes'] == result['electrodes'][k])[0]
            tmp_idx    = numpy.where(result['electrodes'] != result['electrodes'][k])[0]
            electrodes = numpy.where(numpy.max(numpy.abs(templates[:, :, k]), axis=1) > 0)[0]
            idx_2      = []
            overlap_k  = file.get('overlap')[k]
            for idx in tmp_idx:
                if result['electrodes'][idx] in electrodes:
                    idx_2 += [idx]
            for i in idx_1:
                overlap_i = file.get('overlap')[i]
                t1_vs_t1  = overlap_0[i, i]
                t_vs_t1   = overlap_k[i, distances[k, i]]
                for j in idx_2:
                    t2_vs_t2 = overlap_0[j, j]
                    t1_vs_t2 = overlap_i[j, distances[k, i] - distances[k, j]]
                    t_vs_t2  = overlap_k[j, distances[k, j]]
                    M        = numpy.vstack((numpy.hstack((t1_vs_t1, t1_vs_t2)), numpy.hstack((t1_vs_t2, t2_vs_t2))))
                    V        = numpy.hstack((t_vs_t1, t_vs_t2))
                    [a1, a2] = numpy.dot(scipy.linalg.inv(M), V)
                    if numpy.abs(1 - a1) < 0.15 and numpy.abs(1 - a2) < 0.15:
                        if k not in mixtures:
                            mixtures += [k]
            pbar.update(k)
        pbar.finish()
        file.close()
        os.remove(filename)

        templates, amplitudes, result, removed = remove_template(templates, amplitudes, result, numpy.array(mixtures))

    return templates, amplitudes, result, removed, [nb_temp, len(mixtures)]

def detect_peaks(x, mph=None, mpd=1, threshold=0, edge='rising', kpsh=False, valley=False, show=False, ax=None):

    """
    Parameters
    ----------
    x : 1D array_like
        data.
    mph : {None, number}, optional (default = None)
        detect peaks that are greater than minimum peak height.
    mpd : positive integer, optional (default = 1)
        detect peaks that are at least separated by minimum peak distance (in
        number of data).
    threshold : positive number, optional (default = 0)
        detect peaks (valleys) that are greater (smaller) than `threshold`
        in relation to their immediate neighbors.
    edge : {None, 'rising', 'falling', 'both'}, optional (default = 'rising')
        for a flat peak, keep only the rising edge ('rising'), only the
        falling edge ('falling'), both edges ('both'), or don't detect a
        flat peak (None).
    kpsh : bool, optional (default = False)
        keep peaks with same height even if they are closer than `mpd`.
    valley : bool, optional (default = False)
        if True (1), detect valleys (local minima) instead of peaks.
    show : bool, optional (default = False)
        if True (1), plot data in matplotlib figure.
    ax : a matplotlib.axes.Axes instance, optional (default = None).
    """

    x = numpy.atleast_1d(x).astype('float64')
    if x.size < 3:
        return numpy.array([], dtype=numpy.int32)
    if valley:
        x = -x
    # find indices of all peaks
    dx = x[1:] - x[:-1]
    # handle NaN's
    indnan = numpy.where(numpy.isnan(x))[0]
    if indnan.size:
        x[indnan] = numpy.inf
        dx[numpy.where(numpy.isnan(dx))[0]] = numpy.inf
    ine, ire, ife = numpy.array([[], [], []], dtype=numpy.int32)
    if not edge:
        ine = numpy.where((numpy.hstack((dx, 0)) < 0) & (numpy.hstack((0, dx)) > 0))[0]
    else:
        if edge.lower() in ['rising', 'both']:
            ire = numpy.where((numpy.hstack((dx, 0)) <= 0) & (numpy.hstack((0, dx)) > 0))[0]
        if edge.lower() in ['falling', 'both']:
            ife = numpy.where((numpy.hstack((dx, 0)) < 0) & (numpy.hstack((0, dx)) >= 0))[0]
    ind = numpy.unique(numpy.hstack((ine, ire, ife)))
    # handle NaN's
    if ind.size and indnan.size:
        # NaN's and values close to NaN's cannot be peaks
        ind = ind[numpy.in1d(ind, numpy.unique(numpy.hstack((indnan, indnan-1, indnan+1))), invert=True)]
    # first and last values of x cannot be peaks
    if ind.size and ind[0] == 0:
        ind = ind[1:]
    if ind.size and ind[-1] == x.size-1:
        ind = ind[:-1]
    # remove peaks < minimum peak height
    if ind.size and mph is not None:
        ind = ind[x[ind] >= mph]
    # remove peaks - neighbors < threshold
    if ind.size and threshold > 0:
        dx = numpy.min(numpy.vstack([x[ind]-x[ind-1], x[ind]-x[ind+1]]), axis=0)
        ind = numpy.delete(ind, numpy.where(dx < threshold)[0])
    # detect small peaks closer than minimum peak distance
    if ind.size and mpd > 1:
        ind = ind[numpy.argsort(x[ind])][::-1]  # sort ind by peak height
        idel = numpy.zeros(ind.size, dtype=numpy.bool)
        for i in range(ind.size):
            if not idel[i]:
                # keep peaks with the same height if kpsh is True
                idel = idel | (ind >= ind[i] - mpd) & (ind <= ind[i] + mpd) \
                    & (x[ind[i]] > x[ind] if kpsh else True)
                idel[i] = 0  # Keep current peak
        # remove the small peaks and sort back the indices by their occurrence
        ind = numpy.sort(ind[~idel])

    if show:
        if indnan.size:
            x[indnan] = numpy.nan
        if valley:
            x = -x
        pylab.plot(ind, x[ind], 'ro')
        pylab.plot(x, 'k')

    return ind